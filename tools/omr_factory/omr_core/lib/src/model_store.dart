// 인식 모델 내려받기(앱 탑재 S2) — 첫 스캔 때 GitHub 릴리스에서 받아 sha256 검증.
//
// 규칙은 앱의 검수 PDF 저장소(reviewed_pdf_store.dart — 손대지 않음)와 같다:
//  - 주소는 https://github.com/NAKJIKING/free-sheets/releases/download/<tag>/<name>
//    만, 리다이렉트는 최대 5번·release-assets.githubusercontent.com 의
//    /github-production-release-asset/<숫자>/<토큰> 만 따라간다.
//  - 408/429/5xx·소켓 오류는 일시 오류로 보고 다시 시도(Retry-After 존중).
//  - 길이·sha256 이 매니페스트와 같아야만 최종 파일로 rename.
// 모델용으로 바꾼 점(설계 2절):
//  - 저장 위치는 앱이 넘겨주는 영구 폴더(getApplicationSupportDirectory) — 캐시
//    폴더처럼 OS 가 지우지 않게. `<dir>/omr-model-v1/<sha256>.<확장자>`.
//  - 받는 동안 sha256 을 스트리밍으로 계산(파일을 두 번 읽지 않음), 진행률 콜백.
//  - 끊기면 `<sha256>.part` 에서 Range 로 이어받기(서버가 200 으로 답하면 처음부터).
//  - 전체 제한시간 대신 '무활동 30초' 제한(느린 망에서도 21MB 완주).
//  - 검증 실패면 조각을 지우고 처음부터 1회 자동 재시도 후 실패 보고.
import 'dart:async';
import 'dart:io';

import 'package:crypto/crypto.dart';
import 'package:http/http.dart' as http;

/// 받을 파일 하나.
class ModelFile {
  const ModelFile(this.name, this.bytes, this.sha256);
  final String name; // 릴리스 자산 이름(예: omr_crnn_fp32.onnx)
  final int bytes;
  final String sha256; // 소문자 16진 64자

  String get ext => name.contains('.') ? name.substring(name.lastIndexOf('.') + 1) : 'bin';
}

/// 앱에 컴파일해 넣는 매니페스트.
class ModelManifest {
  const ModelManifest({required this.tag, required this.files});
  final String tag;
  final List<ModelFile> files;
}

/// 채택 모델(omr_model_3c4 → FP32 ONNX, 진행일지 2026-09-28) 매니페스트.
/// 릴리스 태그는 아직 게시 전 — 게시는 사장님 승인 후(공개 저장소 자산).
const omrModel3c4 = ModelManifest(tag: 'omr-model-3c4-fp32-01', files: [
  ModelFile('omr_crnn_fp32.onnx', 21831332,
      '6dfc1d66aacfccbcefddb87a674da58a9dab33348b271df58b59467b771e78c2'),
  ModelFile('vocab.json', 23905,
      '05c5be1b82ec1d022769bd6e99fd495ea63aa8141cdb3f3e9ebf5c8e8ed24cd6'),
]);

/// 실패 종류 — 앱이 한국어 안내문으로 바꾼다(설계 5절).
enum ModelFailure {
  /// 인터넷 연결 없음·연결 실패(재시도 후에도).
  offline,

  /// 받은 파일의 길이·sha256 불일치(자동 재시도 후에도).
  corrupt,

  /// 서버가 허용되지 않은 응답(404, 허용 밖 리다이렉트 등).
  server,

  /// 저장 실패(공간 부족 등).
  storage,
}

class ModelStoreException implements Exception {
  ModelStoreException(this.kind, [this.detail = '']);
  final ModelFailure kind;
  final String detail; // 진단용 — 화면에 보이지 않는다
  @override
  String toString() => 'ModelStoreException($kind${detail.isEmpty ? '' : ': $detail'})';
}

/// 주소 허용 규칙(시험에서는 로컬 서버용 규칙으로 바꿔 끼운다).
abstract class AssetUrlPolicy {
  Uri assetUrl(String tag, String name);
  Uri? redirect(String? location);
}

class GithubReleasePolicy implements AssetUrlPolicy {
  const GithubReleasePolicy({this.repo = 'NAKJIKING/free-sheets'});
  final String repo;
  static final _simple = RegExp(r'^[A-Za-z0-9][A-Za-z0-9._-]*$');

  @override
  Uri assetUrl(String tag, String name) {
    if (!_simple.hasMatch(tag) || !_simple.hasMatch(name)) {
      throw ModelStoreException(ModelFailure.server, 'bad asset name');
    }
    return Uri.https('github.com', '/$repo/releases/download/$tag/$name');
  }

  @override
  Uri? redirect(String? location) {
    if (location == null) return null;
    final raw = location.split('?').first;
    if (raw.contains('%') || raw.contains('@') || raw.contains('\\')) return null;
    final u = Uri.tryParse(location);
    if (u == null ||
        u.scheme != 'https' ||
        u.userInfo.isNotEmpty ||
        u.port != 443 ||
        u.hasFragment ||
        u.host != 'release-assets.githubusercontent.com' ||
        !RegExp(r'^/github-production-release-asset/[0-9]+/[A-Za-z0-9_-]+$')
            .hasMatch(u.path)) {
      return null;
    }
    return u;
  }
}

class _Transient implements Exception {
  _Transient(this.delay, this.why);
  final Duration delay;
  final String why;
}

/// 진행률: 지금까지 받은(검증된 조각 포함) 바이트 / 전체 바이트(모든 파일 합).
typedef ModelProgress = void Function(int received, int total);

class ModelStore {
  ModelStore({
    required this.root,
    required this.manifest,
    http.Client? client,
    this.policy = const GithubReleasePolicy(),
    this.connectTimeout = const Duration(seconds: 20),
    this.idleTimeout = const Duration(seconds: 30),
    this.maxAttempts = 3,
  }) : client = client ?? http.Client();

  final Directory root;
  final ModelManifest manifest;
  final http.Client client;
  final AssetUrlPolicy policy;
  final Duration connectTimeout;
  final Duration idleTimeout;
  final int maxAttempts;

  Future<Map<String, File>>? _inFlight;
  final _verified = <String>{}; // 이번 실행에서 검증 끝난 sha256

  Directory get dir => Directory('${root.path}/omr-model-v1');

  File fileFor(ModelFile f) => File('${dir.path}/${f.sha256}.${f.ext}');

  /// 모든 파일이 이미 받아져 있는지(길이만 — 빠른 확인용, 화면 분기).
  bool get looksInstalled =>
      manifest.files.every((f) => fileFor(f).existsSync() && fileFor(f).lengthSync() == f.bytes);

  /// 모든 파일을 준비해 이름→파일로 돌려준다. 동시 호출은 하나로 합친다.
  Future<Map<String, File>> ensure({ModelProgress? onProgress}) =>
      _inFlight ??= _ensure(onProgress).whenComplete(() => _inFlight = null);

  Future<Map<String, File>> _ensure(ModelProgress? onProgress) async {
    try {
      await dir.create(recursive: true);
    } on FileSystemException catch (e) {
      throw ModelStoreException(ModelFailure.storage, e.message);
    }
    final total = manifest.files.fold<int>(0, (s, f) => s + f.bytes);
    var done = 0;
    final out = <String, File>{};
    for (final f in manifest.files) {
      final base = done;
      out[f.name] = await _ensureOne(f, (r) => onProgress?.call(base + r, total));
      done += f.bytes;
      onProgress?.call(done, total);
    }
    return out;
  }

  Future<File> _ensureOne(ModelFile f, void Function(int) progress) async {
    final target = fileFor(f);
    if (await target.exists()) {
      if (_verified.contains(f.sha256)) return target;
      if (await target.length() == f.bytes && await _hashOf(target) == f.sha256) {
        _verified.add(f.sha256);
        return target;
      }
      await target.delete();
    }
    final part = File('${dir.path}/${f.sha256}.part');
    var corruptRetried = false;
    for (var attempt = 0;; attempt++) {
      try {
        await _download(f, part, progress);
      } on _Transient catch (t) {
        if (attempt + 1 >= maxAttempts) {
          throw ModelStoreException(ModelFailure.offline, t.why);
        }
        await Future<void>.delayed(t.delay);
        continue;
      } on FileSystemException catch (e) {
        throw ModelStoreException(ModelFailure.storage, e.message);
      }
      // 다 받음 — 길이·sha256 확인
      if (await part.length() == f.bytes && await _hashOf(part) == f.sha256) {
        try {
          await part.rename(target.path);
        } on FileSystemException catch (e) {
          throw ModelStoreException(ModelFailure.storage, e.message);
        }
        _verified.add(f.sha256);
        return target;
      }
      await part.delete();
      if (corruptRetried) throw ModelStoreException(ModelFailure.corrupt, f.name);
      corruptRetried = true; // 처음부터 1회 더
    }
  }

  static Future<String> _hashOf(File file) async =>
      (await sha256.bind(file.openRead()).first).toString();

  Future<void> _download(ModelFile f, File part, void Function(int) progress) async {
    var have = await part.exists() ? await part.length() : 0;
    if (have > f.bytes) {
      await part.delete();
      have = 0;
    }
    if (have == f.bytes) return; // 조각이 이미 완성(검증은 호출 쪽)
    var uri = policy.assetUrl(manifest.tag, f.name);
    http.StreamedResponse resp;
    for (var redirects = 0;; redirects++) {
      final req = http.Request('GET', uri)
        ..followRedirects = false
        ..headers['Accept'] = 'application/octet-stream';
      if (have > 0) req.headers['Range'] = 'bytes=$have-';
      try {
        resp = await client.send(req).timeout(connectTimeout);
      } on TimeoutException {
        throw _Transient(_backoff(null), 'connect timeout');
      } on SocketException catch (e) {
        throw _Transient(_backoff(null), 'socket ${e.message}');
      } on http.ClientException catch (e) {
        throw _Transient(_backoff(null), 'client ${e.message}');
      }
      if (const {301, 302, 303, 307, 308}.contains(resp.statusCode)) {
        await resp.stream.listen(null, onError: (Object _) {}).cancel();
        final next = policy.redirect(resp.headers['location']);
        if (next == null || redirects == 5) {
          throw ModelStoreException(ModelFailure.server, 'redirect');
        }
        uri = next;
        continue;
      }
      break;
    }
    final code = resp.statusCode;
    if (const {408, 429, 500, 502, 503, 504}.contains(code)) {
      await resp.stream.listen(null, onError: (Object _) {}).cancel();
      throw _Transient(_backoff(resp.headers['retry-after']), 'http $code');
    }
    var append = false;
    if (code == 206 && have > 0) {
      final cr = resp.headers['content-range'] ?? '';
      final m = RegExp(r'^bytes (\d+)-(\d+)/(\d+)$').firstMatch(cr);
      if (m == null ||
          int.parse(m.group(1)!) != have ||
          int.parse(m.group(3)!) != f.bytes) {
        await resp.stream.listen(null, onError: (Object _) {}).cancel();
        await part.delete();
        throw _Transient(Duration.zero, 'bad content-range');
      }
      append = true;
    } else if (code == 200) {
      if (resp.contentLength != null && resp.contentLength != f.bytes) {
        await resp.stream.listen(null, onError: (Object _) {}).cancel();
        throw ModelStoreException(ModelFailure.server, 'length ${resp.contentLength}');
      }
      have = 0; // 서버가 이어받기를 무시 — 처음부터
    } else {
      await resp.stream.listen(null, onError: (Object _) {}).cancel();
      throw ModelStoreException(ModelFailure.server, 'http $code');
    }
    final sink = part.openWrite(mode: append ? FileMode.append : FileMode.write);
    var got = have;
    progress(got);
    try {
      await for (final chunk in resp.stream.timeout(idleTimeout)) {
        got += chunk.length;
        if (got > f.bytes) {
          throw ModelStoreException(ModelFailure.corrupt, 'overflow');
        }
        sink.add(chunk);
        progress(got);
      }
    } on TimeoutException {
      throw _Transient(_backoff(null), 'idle timeout');
    } on SocketException catch (e) {
      throw _Transient(_backoff(null), 'socket ${e.message}');
    } on http.ClientException catch (e) {
      throw _Transient(_backoff(null), 'client ${e.message}');
    } finally {
      await sink.flush();
      await sink.close();
    }
    if (got < f.bytes) throw _Transient(_backoff(null), 'short body');
  }

  static Duration _backoff(String? retryAfter) {
    if (retryAfter != null) {
      final s = int.tryParse(retryAfter);
      if (s != null && s >= 0) return Duration(seconds: s > 30 ? 30 : s);
      try {
        final d = HttpDate.parse(retryAfter).difference(DateTime.now().toUtc());
        return d.isNegative ? Duration.zero : (d > const Duration(seconds: 30) ? const Duration(seconds: 30) : d);
      } on FormatException {
        // 기본 대기
      }
    }
    return const Duration(milliseconds: 250);
  }

  /// 매니페스트에 없는 옛 모델·남은 조각 정리(앱 시작 때 등).
  Future<void> prune() async {
    if (!await dir.exists()) return;
    // 이름으로 비교한다(경로 구분자가 플랫폼마다 달라 전체 경로 비교는 위험).
    final keep = {
      for (final f in manifest.files) ...['${f.sha256}.${f.ext}', '${f.sha256}.part'],
    };
    await for (final e in dir.list(followLinks: false)) {
      final name = e.uri.pathSegments.last;
      if (e is File && !keep.contains(name)) await e.delete();
    }
  }
}
