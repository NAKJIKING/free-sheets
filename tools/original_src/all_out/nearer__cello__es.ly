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
  title = \markup { \fontsize #3 \bold "Nearer, My God, to Thee" }
  subtitle = \markup { \fontsize #0 "Más cerca, oh Dios, de ti · himno" }
  composer = "Lowell Mason"
  arranger = \markup { \fontsize #-1 "Melodía fácil — My Sheet Music" }
  subsubtitle = \markup { \fontsize #0.5 \bold "Violonchelo" }
  tagline = ##f
}
melody = \absolute {
  \clef bass  \key c \major \time 6/4 \tempo 4 = 120
  
  e2. d2 c4 | c2 a,4 a,2. | g,2. c2 e4 | d1~ d2 | e2. d2 c4 | c2 a,4 a,2. | g,2 c4 b,2 d4 | c1~ c2 | g2. a2 g4 | g2 e4 g2. | g2. a2 g4 | g2 e4 d2. | e2. d2 c4 | c2 a,4 a,2. | g,2 c4 b,2 d4 | c1~ c2 | \bar "|."
}
\score {
  <<
    \new Staff \with { \override VerticalAxisGroup.staff-staff-spacing.padding = #5 } { \melody }
  >>
  \layout { \context { \Score \override BarNumber.font-size = #-1 } }
  \midi { }
}
