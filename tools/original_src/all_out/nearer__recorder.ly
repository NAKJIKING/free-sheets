\version "2.24.4"
#(set-global-staff-size 24)
\paper {
  #(set-paper-size "a4")
  top-margin = 16\mm  bottom-margin = 14\mm
  left-margin = 16\mm right-margin = 16\mm
  ragged-bottom = ##t  ragged-last-bottom = ##t
  #(define fonts (set-global-fonts #:roman "Nanum Gothic" #:sans "Nanum Gothic" #:factor (/ staff-height pt 20)))
  oddFooterMarkup = \markup { \fill-line { \fontsize #-3 \line { "" } } }
  evenFooterMarkup = \markup { \fill-line { \fontsize #-3 \line { "" } } }
}
\header {
  title = \markup { \fontsize #3 \bold "Nearer, My God, to Thee" }
  subtitle = \markup { \fontsize #0 "내 주를 가까이 · Nearer, My God, to Thee" }
  composer = "Lowell Mason"
  arranger = \markup { \fontsize #-1 "초급 단선율 · 내 악보함" }
  subsubtitle = \markup { \fontsize #0.5 \bold "리코더" }
  tagline = ##f
}
melody = \absolute {
  \clef treble \transposition c'' \key g \major \time 6/4 \tempo 4 = 120
  
  b'2. a'2 g'4 | g'2 e'4 e'2. | d'2. g'2 b'4 | a'1~ a'2 | b'2. a'2 g'4 | g'2 e'4 e'2. | d'2 g'4 fis'2 a'4 | g'1~ g'2 | d''2. e''2 d''4 | d''2 b'4 d''2. | d''2. e''2 d''4 | d''2 b'4 a'2. | b'2. a'2 g'4 | g'2 e'4 e'2. | d'2 g'4 fis'2 a'4 | g'1~ g'2 | \bar "|."
}
\score {
  <<
    \new Staff \with { \override VerticalAxisGroup.staff-staff-spacing.padding = #5 } { \melody }
  >>
  \layout { \context { \Score \override BarNumber.font-size = #-1 } }
  \midi { }
}
