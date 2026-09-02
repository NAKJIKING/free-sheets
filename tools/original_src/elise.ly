\version "2.24.4"
#(set-global-staff-size 23)
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
  title = \markup { \fontsize #3 \bold "엘리제를 위하여 (A부분)" }
  subtitle = \markup { \fontsize #0 "Für Elise WoO 59 — 첫 부분" }
  composer = "루트비히 판 베토벤 (Ludwig van Beethoven, 1770–1827)"
  arranger = "단선율 초급판 · 내 악보함"
  tagline = ##f
}
melody = \absolute {
  \key a \minor \time 3/8 \tempo 4 = 72
  \partial 8
  e''16 dis''16 | e''16 dis''16 e''16 b'16 d''16 c''16 | a'8. c'16 e'16 a'16 | b'8. e'16 gis'16 b'16 | c''8. e'16 e''16 dis''16 | e''16 dis''16 e''16 b'16 d''16 c''16 | a'8. c'16 e'16 a'16 | b'8. e'16 c''16 b'16 | a'4. | \bar "|."
}
\score {
  <<
    \new Staff \with { \override VerticalAxisGroup.staff-staff-spacing.padding = #5 } { \melody }
    \addlyrics { 미 레♯ 미 레♯ 미 시 레 도 라 도 미 라 시 미 솔♯ 시 도 미 미 레♯ 미 레♯ 미 시 레 도 라 도 미 라 시 미 도 시 라 }
  >>
  \layout { \context { \Score \override BarNumber.font-size = #-1 } }
  \midi { }
}
