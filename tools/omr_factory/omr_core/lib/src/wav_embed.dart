// 인식 결과(미디·토큰)를 첨부 WAV 안의 사설 RIFF 청크로 보관한다.
//
// 왜: 내 악보함 백업(backup_io.backupFiles)은 곡 기록이 참조하는 파일
// (pages·coverPhoto·audioFileName·recordings)만 담는다. 곡 폴더에 따로 둔
// scan.mid 는 백업·복원에서 사라진다. 데이터 모델을 바꾸지 않고 미디를
// 함께 보관하려면 이미 참조되는 파일, 곧 첨부 WAV 안에 넣어야 한다.
// RIFF 규칙상 재생기는 모르는 청크를 건너뛴다 — 'data' 뒤에 붙여 둔다.
//
// 청크 'omrS' 내용: 매직 "OMRS" · 판(u16=1) · 미디 길이(u32) · 미디 ·
// JSON 길이(u32) · JSON(UTF-8: 줄별 토큰·빠르기·모델 판 등). 모두 리틀엔디언.
import 'dart:convert';
import 'dart:typed_data';

const _chunkId = 'omrS';

class ScanPayload {
  ScanPayload(this.midi, this.meta);
  final Uint8List midi;
  final Map<String, dynamic> meta;
}

int _u32(Uint8List b, int o) => ByteData.sublistView(b).getUint32(o, Endian.little);

/// [wav] 끝(data 뒤)에 payload 청크를 붙이고 RIFF 크기를 고친다.
/// 이미 omrS 청크가 있으면 바꿔 넣는다.
Uint8List embedScan(Uint8List wav, ScanPayload p) {
  final base = stripScan(wav);
  final js = utf8.encode(jsonEncode(p.meta));
  final body = BytesBuilder()
    ..add('OMRS'.codeUnits)
    ..add(_le16(1))
    ..add(_le32(p.midi.length))
    ..add(p.midi)
    ..add(_le32(js.length))
    ..add(js);
  final payload = body.takeBytes();
  final out = BytesBuilder()
    ..add(base)
    ..add(_chunkId.codeUnits)
    ..add(_le32(payload.length))
    ..add(payload);
  if (payload.length.isOdd) out.addByte(0); // RIFF 짝수 정렬
  final res = out.takeBytes();
  ByteData.sublistView(res).setUint32(4, res.length - 8, Endian.little);
  return res;
}

/// WAV 에서 payload 를 꺼낸다(없으면 null).
ScanPayload? extractScan(Uint8List wav) {
  final c = _find(wav);
  if (c == null) return null;
  final (start, size) = c;
  final d = ByteData.sublistView(wav, start, start + size);
  if (String.fromCharCodes(wav.sublist(start, start + 4)) != 'OMRS') return null;
  if (d.getUint16(4, Endian.little) != 1) return null;
  final ml = d.getUint32(6, Endian.little);
  final midi = Uint8List.fromList(wav.sublist(start + 10, start + 10 + ml));
  final jl = d.getUint32(10 + ml, Endian.little);
  final js = utf8.decode(wav.sublist(start + 14 + ml, start + 14 + ml + jl));
  return ScanPayload(midi, jsonDecode(js) as Map<String, dynamic>);
}

/// omrS 청크를 뺀 순수 WAV.
Uint8List stripScan(Uint8List wav) {
  final c = _find(wav);
  if (c == null) return wav;
  final (start, size) = c;
  final hdr = start - 8;
  final end = start + size + (size.isOdd ? 1 : 0);
  final res = Uint8List.fromList([...wav.sublist(0, hdr), ...wav.sublist(end)]);
  ByteData.sublistView(res).setUint32(4, res.length - 8, Endian.little);
  return res;
}

/// (청크 내용 시작, 크기) — RIFF 청크를 순회해 omrS 를 찾는다.
(int, int)? _find(Uint8List wav) {
  if (wav.length < 12 ||
      String.fromCharCodes(wav.sublist(0, 4)) != 'RIFF' ||
      String.fromCharCodes(wav.sublist(8, 12)) != 'WAVE') {
    throw const FormatException('WAV 가 아니다');
  }
  var o = 12;
  while (o + 8 <= wav.length) {
    final id = String.fromCharCodes(wav.sublist(o, o + 4));
    final size = _u32(wav, o + 4);
    if (id == _chunkId) return (o + 8, size);
    o += 8 + size + (size.isOdd ? 1 : 0);
  }
  return null;
}

List<int> _le16(int v) => [v & 0xff, (v >> 8) & 0xff];
List<int> _le32(int v) => [v & 0xff, (v >> 8) & 0xff, (v >> 16) & 0xff, (v >> 24) & 0xff];
