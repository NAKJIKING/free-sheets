// 어휘 — vocab.json(줄 번호+1 = 클래스 id, 0 = CTC blank) → [음고, 길이, 붙임줄].
import 'dart:convert';

/// 토큰 하나. pitch>0 음표(미디 키), 0 쉼표, <0 기호
/// (−1 |: −2 :| −3 1번괄호 −4 2번괄호 −5 빠르기 마커 −6 f −7 p −8 mf
/// −9 크레셴도 시작 −10 크레셴도 끝). dur 는 4분음표=12 틱.
class Tok {
  const Tok(this.pitch, this.dur, this.tie);
  final int pitch;
  final int dur;
  final bool tie;

  bool get isNote => pitch > 0;
  bool get isRest => pitch == 0;
  bool get isSymbol => pitch < 0;

  List<int> toJson() => [pitch, dur, tie ? 1 : 0];
  factory Tok.fromJson(List<dynamic> j) =>
      Tok(j[0] as int, j[1] as int, (j[2] as int) != 0);

  @override
  bool operator ==(Object o) =>
      o is Tok && o.pitch == pitch && o.dur == dur && o.tie == tie;
  @override
  int get hashCode => Object.hash(pitch, dur, tie);
  @override
  String toString() => '($pitch,$dur${tie ? ',~' : ''})';
}

const repStart = -1, repEnd = -2, volta1 = -3, volta2 = -4;
const tempoMark = -5, dynF = -6, dynP = -7, dynMf = -8;
const crescStart = -9, crescEnd = -10;

class Vocab {
  Vocab(this.itos);
  final List<Tok> itos; // 인덱스 = 클래스 id − 1

  factory Vocab.fromJsonString(String s) => Vocab([
        for (final t in jsonDecode(s) as List) Tok.fromJson(t as List),
      ]);

  int get numClasses => itos.length + 1; // + blank

  /// CTC id 열 → 토큰 열 (blank 0 은 디코드에서 이미 빠져 있다).
  List<Tok> tokens(List<int> ids) => [for (final k in ids) itos[k - 1]];
}
