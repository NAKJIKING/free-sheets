\version "2.24.4"
#(set-global-staff-size 22)
\paper {
  #(set-paper-size "a4")
  top-margin = 16\mm  bottom-margin = 14\mm
  left-margin = 16\mm right-margin = 16\mm
  ragged-bottom = ##t  ragged-last-bottom = ##t
  property-defaults.fonts.roman = "Nanum Gothic"
  oddFooterMarkup = \markup { \fill-line { \fontsize #-3 \line { "" } } }
  evenFooterMarkup = \markup { \fill-line { \fontsize #-3 \line { "" } } }
}
\header {
  title = \markup { \fontsize #3 \bold "터키 행진곡 주제" }
  subtitle = \markup { \fontsize #0 "Rondo alla turca — 피아노 소나타 K.331 3악장" }
  composer = "볼프강 아마데우스 모차르트 (Wolfgang Amadeus Mozart, 1756–1791)"
  arranger = "단선율 초급판 · 내 악보함"
  tagline = ##f
}
melody = \absolute {
  \key a \minor \time 2/4 \tempo 4 = 120
  \partial 4
  b'16 a'16 gis'16 a'16 | c''4 d''16 c''16 b'16 c''16 | e''4 f''16 e''16 dis''16 e''16 | b''16 a''16 gis''16 a''16 b''16 a''16 gis''16 a''16 | c'''4 a''8 c'''8 | b''8 a''8 g''8 a''8 | b''8 a''8 g''8 a''8 | b''8 a''8 g''8 fis''8 | e''2 | \bar "|."
}
\score {
  <<
    \new Staff \with { \override VerticalAxisGroup.staff-staff-spacing.padding = #5 } { \melody }
    \addlyrics { 시 라 솔♯ 라 도 레 도 시 도 미 파 미 레♯ 미 시 라 솔♯ 라 시 라 솔♯ 라 도 라 도 시 라 솔 라 시 라 솔 라 시 라 솔 파♯ 미 }
  >>
  \layout { \context { \Score \override BarNumber.font-size = #-1 } }
  \midi { }
}
