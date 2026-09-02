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
  title = \markup { \fontsize #3 \bold "송어" }
  subtitle = \markup { \fontsize #0 "Die Forelle D.550 — 노래 선율" }
  composer = "프란츠 슈베르트 (Franz Schubert, 1797–1828)"
  arranger = "단선율 초급판 · 내 악보함"
  tagline = ##f
}
melody = \absolute {
  \key c \major \time 2/4 \tempo 4 = 96
  \partial 8
  g'8 | c''8 c''8 e''8 e''8 | c''4 g'8 g'8 | g'8. g'16 d''16 c''16 b'16 a'16 | g'4. g'8 | c''8 c''8 e''8 e''8 | c''4 g'8 c''8 | b'8 a'16 b'16 c''8 fis'8 | g'4. g'8 | b'8 b'8 c''16 b'16 a'16 b'16 | c''4 g'8 c''8 | b'8 b'8 b'16 f''16 d''16 b'16 | c''4. c''8 | a'8 a'8 a'8 c''8 | c''4 g'8 g'8 | g'8. g'16 d''8 b'8 | c''2 | \bar "|."
}
\score {
  <<
    \new Staff \with { \override VerticalAxisGroup.staff-staff-spacing.padding = #5 } { \melody }
    \addlyrics { 솔 도 도 미 미 도 솔 솔 솔 솔 레 도 시 라 솔 솔 도 도 미 미 도 솔 도 시 라 시 도 파♯ 솔 솔 시 시 도 시 라 시 도 솔 도 시 시 시 파 레 시 도 도 라 라 라 도 도 솔 솔 솔 솔 레 시 도 }
  >>
  \layout { \context { \Score \override BarNumber.font-size = #-1 } }
  \midi { }
}
