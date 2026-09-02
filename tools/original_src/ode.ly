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
  title = \markup { \fontsize #3 \bold "환희의 송가" }
  subtitle = \markup { \fontsize #0 "Ode to Joy — 교향곡 9번 4악장 주제" }
  composer = "루트비히 판 베토벤 (Ludwig van Beethoven, 1770–1827)"
  arranger = "단선율 초급판 · 내 악보함"
  tagline = ##f
}
melody = \absolute {
  \key g \major \time 4/4 \tempo 4 = 104
  
  b'4 b'4 c''4 d''4 | d''4 c''4 b'4 a'4 | g'4 g'4 a'4 b'4 | b'4. a'8 a'2 | b'4 b'4 c''4 d''4 | d''4 c''4 b'4 a'4 | g'4 g'4 a'4 b'4 | a'4. g'8 g'2 | a'4 a'4 b'4 g'4 | a'4 b'8 c''8 b'4 g'4 | a'4 b'8 c''8 b'4 a'4 | g'4 a'4 d'2 | b'4 b'4 c''4 d''4 | d''4 c''4 b'4 a'4 | g'4 g'4 a'4 b'4 | a'4. g'8 g'2 | \bar "|."
}
\score {
  <<
    \new Staff \with { \override VerticalAxisGroup.staff-staff-spacing.padding = #5 } { \melody }
    \addlyrics { 시 시 도 레 레 도 시 라 솔 솔 라 시 시 라 라 시 시 도 레 레 도 시 라 솔 솔 라 시 라 솔 솔 라 라 시 솔 라 시 도 시 솔 라 시 도 시 라 솔 라 레 시 시 도 레 레 도 시 라 솔 솔 라 시 라 솔 솔 }
  >>
  \layout { \context { \Score \override BarNumber.font-size = #-1 } }
  \midi { }
}
