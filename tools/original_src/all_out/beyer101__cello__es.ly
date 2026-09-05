\version "2.24.4"
#(set-global-staff-size 24)
\paper {
  #(set-paper-size "a4")
  top-margin = 16\mm  bottom-margin = 14\mm
  left-margin = 16\mm right-margin = 16\mm
  ragged-bottom = ##t  ragged-last-bottom = ##t
  #(define fonts (set-global-fonts #:roman "C059" #:sans "C059" #:factor (/ staff-height pt 20)))
  oddFooterMarkup = \markup { \fill-line { \fontsize #-3 \line { "" } } }
  evenFooterMarkup = \markup { \fill-line { \fontsize #-3 \line { "" } } }
}
\header {
  title = \markup { \fontsize #1 \bold "Vorschule im Klavierspiel, Op.101" }
  subtitle = \markup { \fontsize #0 "Escuela preparatoria de piano, op.101 · melodía" }
  composer = "Ferdinand Beyer"
  arranger = \markup { \fontsize #-1 "Melodía fácil — My Sheet Music" }
  subsubtitle = \markup { \fontsize #0.5 \bold "Violonchelo" }
  tagline = ##f
}
melody = \absolute {
  \clef bass  \key c \major \time 4/4 \tempo 4 = 114
  
  g,1 | d2 c2 | b,4 d4 c4 b,4 | a,1 | g,1 | d2 c2 | b,4 d4 c4 a,4 | g,1 | a,1 | g,4 d4 c4 b,4 | a,1 | d4 g,4 b,4 a,4 | g,1 | d2 c2 | b,4 d4 c4 a,4 | g,1 | \bar "|."
}
\score {
  <<
    \new Staff \with { \override VerticalAxisGroup.staff-staff-spacing.padding = #5 } { \melody }
  >>
  \layout { \context { \Score \override BarNumber.font-size = #-1 } }
  \midi { }
}
