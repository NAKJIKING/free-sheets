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
  title = \markup { \fontsize #3 \bold "반짝반짝 작은 별" }
  subtitle = \markup { \fontsize #0 "Twinkle, Twinkle, Little Star — 프랑스 민요 (모차르트 변주곡 K.265 주제)" }
  composer = "프랑스 민요 · 볼프강 아마데우스 모차르트 편 (1756–1791)"
  arranger = "단선율 초급판 · 내 악보함"
  tagline = ##f
}
melody = \absolute {
  \key c \major \time 4/4 \tempo 4 = 100
  
  c'4 c'4 g'4 g'4 | a'4 a'4 g'2 | f'4 f'4 e'4 e'4 | d'4 d'4 c'2 | g'4 g'4 f'4 f'4 | e'4 e'4 d'2 | g'4 g'4 f'4 f'4 | e'4 e'4 d'2 | c'4 c'4 g'4 g'4 | a'4 a'4 g'2 | f'4 f'4 e'4 e'4 | d'4 d'4 c'2 | \bar "|."
}
\score {
  <<
    \new Staff \with { \override VerticalAxisGroup.staff-staff-spacing.padding = #5 } { \melody }
    \addlyrics { 도 도 솔 솔 라 라 솔 파 파 미 미 레 레 도 솔 솔 파 파 미 미 레 솔 솔 파 파 미 미 레 도 도 솔 솔 라 라 솔 파 파 미 미 레 레 도 }
  >>
  \layout { \context { \Score \override BarNumber.font-size = #-1 } }
  \midi { }
}
