// model_store — 로컬 HTTP 서버로 받기·이어받기·검증·재시도·리다이렉트 규칙 시험.
import 'dart:async';
import 'dart:io';
import 'dart:math';
import 'dart:typed_data';

import 'package:crypto/crypto.dart';
import 'package:omr_core/omr_core.dart';
import 'package:test/test.dart';

/// 로컬 서버용 규칙: http://127.0.0.1:<port>/dl/<tag>/<name>, 리다이렉트는 /asset/<숫자> 만.
class LocalPolicy implements AssetUrlPolicy {
  LocalPolicy(this.port);
  final int port;
  @override
  Uri assetUrl(String tag, String name) => Uri.parse('http://127.0.0.1:$port/dl/$tag/$name');
  @override
  Uri? redirect(String? location) {
    final u = location == null ? null : Uri.tryParse(location);
    if (u == null || u.host != '127.0.0.1' || !RegExp(r'^/asset/[0-9]+$').hasMatch(u.path)) {
      return null;
    }
    return u;
  }
}

class Server {
  late HttpServer http;
  late Uint8List body;
  final rangeHeaders = <String?>[];
  int requests = 0;

  /// 요청 번호(0부터) → 동작: 'ok' | 'cut' | 'ignore-range' | '503' | 'redirect' | 'bad-redirect'
  String Function(int n) plan = (_) => 'ok';

  Future<void> start(Uint8List data) async {
    body = data;
    http = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    http.listen((req) async {
      final n = requests++;
      final r = req.response;
      final act = req.uri.path.startsWith('/asset/') ? 'ok' : plan(n);
      rangeHeaders.add(req.headers.value('range'));
      if (act == '503') {
        r.statusCode = 503;
        r.headers.set('retry-after', '0');
        await r.close();
        return;
      }
      if (act == 'redirect' || act == 'bad-redirect') {
        r.statusCode = 302;
        r.headers.set('location',
            act == 'redirect' ? 'http://127.0.0.1:${http.port}/asset/77' : 'http://127.0.0.1:${http.port}/evil');
        await r.close();
        return;
      }
      final range = req.headers.value('range');
      var start = 0;
      if (range != null && act != 'ignore-range') {
        start = int.parse(RegExp(r'bytes=(\d+)-').firstMatch(range)!.group(1)!);
        r.statusCode = 206;
        r.headers.set('content-range', 'bytes $start-${body.length - 1}/${body.length}');
      }
      r.contentLength = body.length - start;
      if (act == 'cut') {
        // 절반만 보내고 연결을 끊는다
        final s = await r.detachSocket(writeHeaders: true);
        s.add(body.sublist(start, start + (body.length - start) ~/ 2));
        await s.flush();
        s.destroy();
        return;
      }
      r.add(body.sublist(start));
      await r.close();
    });
  }

  Future<void> stop() => http.close(force: true);
}

void main() {
  late Directory tmp;
  late Server srv;
  final data = Uint8List.fromList(List.generate(300000, (i) => Random(1).nextInt(256) ^ (i & 0xff)));
  final hash = sha256.convert(data).toString();
  ModelManifest manifest([String? h]) =>
      ModelManifest(tag: 't1', files: [ModelFile('m.onnx', data.length, h ?? hash)]);

  setUp(() async {
    tmp = await Directory.systemTemp.createTemp('omr_ms_');
    srv = Server();
    await srv.start(data);
  });
  tearDown(() async {
    await srv.stop();
    await tmp.delete(recursive: true);
  });

  ModelStore store([ModelManifest? m]) => ModelStore(
      root: tmp, manifest: m ?? manifest(), policy: LocalPolicy(srv.http.port),
      idleTimeout: const Duration(seconds: 2));

  test('받기 성공 — 진행률 단조 증가, 최종 파일 이름 = sha256', () async {
    final seen = <int>[];
    final files = await store().ensure(onProgress: (r, t) {
      expect(t, data.length);
      seen.add(r);
    });
    expect(await files['m.onnx']!.readAsBytes(), data);
    expect(files['m.onnx']!.path, endsWith('$hash.onnx'));
    expect(seen.last, data.length);
    for (var i = 1; i < seen.length; i++) {
      expect(seen[i] >= seen[i - 1], isTrue);
    }
  });

  test('끊기면 Range 로 이어받기', () async {
    srv.plan = (n) => n == 0 ? 'cut' : 'ok';
    final files = await store().ensure();
    expect(await files['m.onnx']!.readAsBytes(), data);
    expect(srv.rangeHeaders[0], isNull);
    expect(srv.rangeHeaders[1], startsWith('bytes='));
  });

  test('서버가 Range 를 무시하면 처음부터', () async {
    srv.plan = (n) => n == 0 ? 'cut' : 'ignore-range';
    final files = await store().ensure();
    expect(await files['m.onnx']!.readAsBytes(), data);
  });

  test('503 은 다시 시도', () async {
    srv.plan = (n) => n == 0 ? '503' : 'ok';
    expect(await (await store().ensure())['m.onnx']!.readAsBytes(), data);
  });

  test('허용된 리다이렉트는 따라가고, 허용 밖이면 server 실패', () async {
    srv.plan = (_) => 'redirect';
    expect(await (await store().ensure())['m.onnx']!.readAsBytes(), data);
    await Directory('${tmp.path}/omr-model-v1').delete(recursive: true);
    srv.plan = (_) => 'bad-redirect';
    await expectLater(store().ensure(),
        throwsA(isA<ModelStoreException>().having((e) => e.kind, 'kind', ModelFailure.server)));
  });

  test('sha256 불일치 → 처음부터 1회 재시도 후 corrupt, 최종 파일 없음', () async {
    final s = store(manifest('0' * 64));
    await expectLater(s.ensure(),
        throwsA(isA<ModelStoreException>().having((e) => e.kind, 'kind', ModelFailure.corrupt)));
    expect(srv.requests, 2);
    expect(Directory('${tmp.path}/omr-model-v1').listSync(), isEmpty);
  });

  test('연결 불가 → offline', () async {
    final port = srv.http.port;
    await srv.stop();
    final s = ModelStore(root: tmp, manifest: manifest(), policy: LocalPolicy(port),
        connectTimeout: const Duration(seconds: 2));
    await expectLater(s.ensure(),
        throwsA(isA<ModelStoreException>().having((e) => e.kind, 'kind', ModelFailure.offline)));
    await srv.start(data); // tearDown 용
  });

  test('이미 받은 파일은 네트워크 없이 검증만, 손상되면 다시 받기', () async {
    await store().ensure();
    final before = srv.requests;
    final s2 = store();
    await s2.ensure();
    expect(srv.requests, before);
    expect(s2.looksInstalled, isTrue);
    // 손상 → 새 저장소(새 실행)에서 다시 받음
    final f = File('${tmp.path}/omr-model-v1/$hash.onnx');
    final bad = await f.readAsBytes();
    bad[10] ^= 0xff;
    await f.writeAsBytes(bad);
    await store().ensure();
    expect(srv.requests, before + 1);
    expect(await f.readAsBytes(), data);
  });

  test('GitHub 규칙 — 자산 주소·리다이렉트 허용 범위(검수 PDF 와 같은 규칙)', () {
    const p = GithubReleasePolicy();
    expect(p.assetUrl('omr-model-3c4-fp32-01', 'omr_crnn_fp32.onnx').toString(),
        'https://github.com/NAKJIKING/free-sheets/releases/download/omr-model-3c4-fp32-01/omr_crnn_fp32.onnx');
    expect(() => p.assetUrl('../x', 'a.onnx'), throwsA(isA<ModelStoreException>()));
    const ok = 'https://release-assets.githubusercontent.com/github-production-release-asset/123/abc-DEF_9?sp=r&sig=x';
    expect(p.redirect(ok), isNotNull);
    for (final bad in [
      null,
      'http://release-assets.githubusercontent.com/github-production-release-asset/123/abc',
      'https://evil.example.com/github-production-release-asset/123/abc',
      'https://release-assets.githubusercontent.com/other/123/abc',
      'https://user@release-assets.githubusercontent.com/github-production-release-asset/1/a',
      'https://release-assets.githubusercontent.com:8443/github-production-release-asset/1/a',
      'https://release-assets.githubusercontent.com/github-production-release-asset/1/a%2F..',
    ]) {
      expect(p.redirect(bad), isNull, reason: '$bad');
    }
  });

  test('prune — 매니페스트 밖 파일만 지움', () async {
    final s = store();
    await s.ensure();
    final old = File('${tmp.path}/omr-model-v1/${'a' * 64}.onnx')..writeAsBytesSync([1]);
    await s.prune();
    expect(old.existsSync(), isFalse);
    expect(s.looksInstalled, isTrue);
  });
}
