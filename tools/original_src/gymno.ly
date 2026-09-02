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
  title = \markup { \fontsize #3 \bold "짐노페디 1번" }
  subtitle = \markup { \fontsize #0 "Gymnopédie No.1 — 선율" }
  composer = "에릭 사티 (Erik Satie, 1866–1925)"
  arranger = "단선율 초급판 · 내 악보함"
  tagline = ##f
}
melody = \absolute {
  \key c \major \time 3/4 \tempo 4 = 72
  \partial 2
  e''4 g''4 | f''4 e''4 b'4 | a'4 b'4 c''4 | g'2. | r2. | r4 e''4 g''4 | f''4 e''4 b'4 | a'4 b'4 c''4 | g'2. | b'2. | e''2. | r2. | g'4 a'4 bes'4 | d''4 c''4 a'4 | c''4 bes'4 a'4 | c''2. | \bar "|."
}
\score {
  <<
    \new Staff \with { \override VerticalAxisGroup.staff-staff-spacing.padding = #5 } { \melody }
    \addlyrics { 미 솔 파 미 시 라 시 도 솔 미 솔 파 미 시 라 시 도 솔 시 미 솔 라 시♭ 레 도 라 도 시♭ 라 도 }
  >>
  \layout { \context { \Score \override BarNumber.font-size = #-1 } }
  \midi { }
}
