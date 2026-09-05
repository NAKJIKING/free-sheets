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
  title = \markup { \fontsize #3 \bold "Amazing Grace" }
  subtitle = \markup { \fontsize #0 "Sublime gracia · himno" }
  composer = "Traditional"
  arranger = \markup { \fontsize #-1 "Melodía fácil — My Sheet Music" }
  subsubtitle = \markup { \fontsize #0.5 \bold "Violonchelo" }
  tagline = ##f
}
melody = \absolute {
  \clef bass  \key c \major \time 3/4 \tempo 4 = 120
  
  g,4 c2 | e8 c8 e2 | d4 c2 | a,4 g,2 | g,4 c2 | e8 c8 e2 | d4 g2~ | g2. | e4 g4. e8 | g8 e8 c2 | g,4 a,4. c8 | c8 a,8 g,2 | g,4 c2 | e8 c8 e2 | d4 c2~ | c2. | \bar "|."
}
\score {
  <<
    \new Staff \with { \override VerticalAxisGroup.staff-staff-spacing.padding = #5 } { \melody }
  >>
  \layout { \context { \Score \override BarNumber.font-size = #-1 } }
  \midi { }
}
