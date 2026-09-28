// 회색 float 이미지 (0~1) — 파이프라인 공용 자료형.
// 파이썬 PIL 'L' + numpy float32 경로와 짝을 맞춘다.
import 'dart:typed_data';

import 'package:image/image.dart' as im;

class GrayF32 {
  GrayF32(this.w, this.h) : data = Float32List(w * h);
  GrayF32.of(this.w, this.h, this.data);

  final int w;
  final int h;
  final Float32List data;

  double at(int x, int y) => data[y * w + x];
  void set(int x, int y, double v) => data[y * w + x] = v;

  GrayF32 clone() => GrayF32.of(w, h, Float32List.fromList(data));

  GrayF32 crop(int x0, int y0, int x1, int y1) {
    final ow = x1 - x0, oh = y1 - y0;
    final out = GrayF32(ow, oh);
    for (var y = 0; y < oh; y++) {
      out.data.setRange(y * ow, y * ow + ow, data, (y0 + y) * w + x0);
    }
    return out;
  }
}

/// JPEG 바이트 → 회색 0~1 (밝음=1). EXIF 회전 반영(PIL exif_transpose 대응).
/// PIL convert('L') = ITU-R 601-2 (299R+587G+114B)/1000 정수 연산과 맞춘다.
GrayF32 decodeGray(Uint8List bytes) {
  var img = im.decodeImage(bytes)!;
  img = im.bakeOrientation(img);
  final g = GrayF32(img.width, img.height);
  var i = 0;
  for (final p in img) {
    final l = (p.r.toInt() * 299 + p.g.toInt() * 587 + p.b.toInt() * 114) ~/
        1000;
    g.data[i++] = l / 255.0;
  }
  return g;
}
