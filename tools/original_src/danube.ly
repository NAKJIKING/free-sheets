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
  title = \markup { \fontsize #3 \bold "아름답고 푸른 도나우 주제" }
  subtitle = \markup { \fontsize #0 "An der schönen blauen Donau Op.314 — 왈츠 주제" }
  composer = "요한 슈트라우스 2세 (Johann Strauss II, 1825–1899)"
  arranger = "단선율 초급판 · 내 악보함"
  tagline = ##f
}
melody = \absolute {
  \key c \major \time 3/4 \tempo 4 = 160
  
  c'4 c'4 e'4 | g'4 g'2 | g''4 g''2 | e''4 e''2 | c'4 c'4 e'4 | g'4 g'2 | g''4 g''2 | f''4 f''2 | b4 b4 d'4 | a'4 a'2 | a''4 a''2 | f''4 f''2 | b4 b4 d'4 | a'4 a'2 | a''4 a''2 | e''4 e''2 | c'4 c'4 e'4 | g'4 c''2 | c'''4 c'''2 | g''4 g''2 | c'4 c'4 e'4 | g'4 c''2 | c'''4 c'''2 | a''4 a''2 | d'4 d'4 f'4 | a'4 a'2~ | a'2 fis'4 | g'4 e''2~ | e''2 c''4 | e'4 e'2 | d'4 a'2 | g'4 c'2 | \bar "|."
}
\score {
  <<
    \new Staff \with { \override VerticalAxisGroup.staff-staff-spacing.padding = #5 } { \melody }
    \addlyrics { 도 도 미 솔 솔 솔 솔 미 미 도 도 미 솔 솔 솔 솔 파 파 시 시 레 라 라 라 라 파 파 시 시 레 라 라 라 라 미 미 도 도 미 솔 도 도 도 솔 솔 도 도 미 솔 도 도 도 라 라 레 레 파 라 라 파♯ 솔 미 도 미 미 레 라 솔 도 }
  >>
  \layout { \context { \Score \override BarNumber.font-size = #-1 } }
  \midi { }
}
