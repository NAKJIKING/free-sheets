\version "2.24.4"
#(set-global-staff-size 24)
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
  title = \markup { \fontsize #3 \bold "그린슬리브즈" }
  subtitle = \markup { \fontsize #0 "Greensleeves — 영국 민요" }
  composer = "영국 전통 민요 (16세기)"
  arranger = "단선율 초급판 · 내 악보함"
  tagline = ##f
}
melody = \absolute {
  \key a \minor \time 6/8 \tempo 4 = 60
  \partial 8
  a'8 | c''4 d''8 e''8. f''16 e''8 | d''4 b'8 g'8. a'16 b'8 | c''4 a'8 a'8. gis'16 a'8 | b'4. e'4 a'8 | c''4 d''8 e''8. f''16 e''8 | d''4 b'8 g'8. a'16 b'8 | c''8. b'16 a'8 gis'8. fis'16 gis'8 | a'4. a'4. | g''4. g''8. fis''16 e''8 | d''4 b'8 g'8. a'16 b'8 | c''4 a'8 a'8. gis'16 a'8 | b'4 gis'8 e'4. | g''4. g''8. f''16 e''8 | d''4 b'8 g'8. a'16 b'8 | c''8. b'16 a'8 gis'8. fis'16 gis'8 | a'4. a'4. | \bar "|."
}
\score {
  <<
    \new Staff \with { \override VerticalAxisGroup.staff-staff-spacing.padding = #5 } { \melody }
    \addlyrics { 라 도 레 미 파 미 레 시 솔 라 시 도 라 라 솔♯ 라 시 미 라 도 레 미 파 미 레 시 솔 라 시 도 시 라 솔♯ 파♯ 솔♯ 라 라 솔 솔 파♯ 미 레 시 솔 라 시 도 라 라 솔♯ 라 시 솔♯ 미 솔 솔 파 미 레 시 솔 라 시 도 시 라 솔♯ 파♯ 솔♯ 라 라 }
  >>
  \layout { \context { \Score \override BarNumber.font-size = #-1 } }
  \midi { }
}
