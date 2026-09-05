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
  title = \markup { \fontsize #3 \bold "Rock of Ages" }
  subtitle = \markup { \fontsize #0 "Rocha eterna · hino" }
  composer = "Thomas Hastings"
  arranger = \markup { \fontsize #-1 "Melodia fácil — My Sheet Music" }
  subsubtitle = \markup { \fontsize #0.5 \bold "Violoncelo" }
  tagline = ##f
}
melody = \absolute {
  \clef bass  \key c \major \time 6/4 \tempo 4 = 120
  
  g,4. a,8 g,2 e,2 | c4. a,8 g,1 | c4. d8 e2. d4 | c4 b,4 c1 | b,4. c8 d2. d4 | b,4 g,4 c1 | b,4. c8 d2. d4 | b,4 g,4 c1 | g,4. a,8 g,2 e,2 | c4. a,8 g,1 | c4. d8 e2. d4 | c4 b,4 c1 | \bar "|."
}
\score {
  <<
    \new Staff \with { \override VerticalAxisGroup.staff-staff-spacing.padding = #5 } { \melody }
  >>
  \layout { \context { \Score \override BarNumber.font-size = #-1 } }
  \midi { }
}
