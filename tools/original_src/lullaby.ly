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
  title = \markup { \fontsize #3 \bold "브람스 자장가" }
  subtitle = \markup { \fontsize #0 "Wiegenlied Op.49 No.4" }
  composer = "요하네스 브람스 (Johannes Brahms, 1833–1897)"
  arranger = "단선율 초급판 · 내 악보함"
  tagline = ##f
}
melody = \absolute {
  \key c \major \time 3/4 \tempo 4 = 80
  \partial 4
  e'8 e'8 | g'4. e'8 e'4 | g'2 e'8 g'8 | c''4 b'4. a'8 | a'4 g'4 d'8 e'8 | f'4 d'4 d'8 e'8 | f'2 d'8 f'8 | b'8 a'8 g'4 b'4 | c''2 c'8 c'8 | c''2 a'8 f'8 | g'2 e'8 c'8 | f'4 g'4 a'4 | e'8 g'4. c'8 c'8 | c''2 a'8 f'8 | g'2 e'8 c'8 | f'8 g'16 f'16 e'4 d'4 | c'2. | \bar "|."
}
\score {
  <<
    \new Staff \with { \override VerticalAxisGroup.staff-staff-spacing.padding = #5 } { \melody }
    \addlyrics { 미 미 솔 미 미 솔 미 솔 도 시 라 라 솔 레 미 파 레 레 미 파 레 파 시 라 솔 시 도 도 도 도 라 파 솔 미 도 파 솔 라 미 솔 도 도 도 라 파 솔 미 도 파 솔 파 미 레 도 }
  >>
  \layout { \context { \Score \override BarNumber.font-size = #-1 } }
  \midi { }
}
