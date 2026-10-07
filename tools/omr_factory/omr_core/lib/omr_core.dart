/// 악보 사진 인식 순수 다트 코어. 사용 흐름은 [Scanner.scan] 참고.
library;

export 'src/ctc.dart';
export 'src/model_store.dart';
export 'src/monophony.dart';
export 'src/parts.dart';
export 'src/pipeline/gray.dart' show GrayF32, decodeGray;
export 'src/pipeline/photo_prep.dart' show LineCrop, extractLines;
export 'src/pipeline/prep.dart' show normalizePhoto, staffQ;
export 'src/scanner.dart';
export 'src/score.dart';
export 'src/select.dart';
export 'src/vocab.dart';
export 'src/wav_embed.dart';
