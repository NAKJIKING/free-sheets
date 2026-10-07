// CTC 그리디 디코드 + 줄 신뢰도 (model.greedy_decode · evaluate_duet.decode_conf 대응).
import 'dart:math' as math;
import 'dart:typed_data';

/// 한 줄의 디코드 결과.
class LineDecode {
  LineDecode(this.ids, this.conf, this.frames);

  /// blank(0) 와 연속 중복을 접은 클래스 id 열.
  final List<int> ids;

  /// 프레임별 최대 소프트맥스 확률의 평균.
  final double conf;

  /// 사용한 프레임 수 (= 입력 폭 ~/ 4, 로짓 길이로 상한).
  final int frames;
}

/// [logits]: (T × C) 행 우선 float32. [inputW]: 정규화 텐서 폭 — 유효
/// 프레임은 inputW ~/ 4 (모델 다운샘플 4).
LineDecode greedyDecode(Float32List logits, int numClasses, int inputW) {
  final total = logits.length ~/ numClasses;
  final t = math.max(1, math.min(total, inputW ~/ 4));
  final ids = <int>[];
  var prev = 0;
  var confSum = 0.0;
  for (var f = 0; f < t; f++) {
    final o = f * numClasses;
    var am = 0;
    var mx = logits[o];
    for (var c = 1; c < numClasses; c++) {
      final v = logits[o + c];
      if (v > mx) {
        mx = v;
        am = c;
      }
    }
    var se = 0.0;
    for (var c = 0; c < numClasses; c++) {
      se += math.exp(logits[o + c] - mx);
    }
    confSum += 1.0 / se;
    if (am != prev && am != 0) ids.add(am);
    prev = am;
  }
  return LineDecode(ids, confSum / t, t);
}
