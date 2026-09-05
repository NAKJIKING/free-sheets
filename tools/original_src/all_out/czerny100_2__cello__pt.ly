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
  title = \markup { \fontsize #2 \bold "100 Recreations, Op.139 No.2" }
  subtitle = \markup { \fontsize #0 "100 recreações, No.2 · melodia" }
  composer = "Carl Czerny"
  arranger = \markup { \fontsize #-1 "Melodia fácil — My Sheet Music" }
  subsubtitle = \markup { \fontsize #0.5 \bold "Violoncelo" }
  tagline = ##f
}
melody = \absolute {
  \clef bass  \key c \major \time 3/4 \tempo 4 = 120
  
  c4 d4 e4 | e4 e4 e4 | d4 e4 f4 | f4 f4 f4 | e4 f4 g4 | g4 g4 g4 | g4 f4 d4 | c2. | c4 d4 e4 | e4 e4 e4 | d4 e4 f4 | f4 f4 f4 | \bar "|."
}
\score {
  <<
    \new Staff \with { \override VerticalAxisGroup.staff-staff-spacing.padding = #5 } { \melody }
  >>
  \layout { \context { \Score \override BarNumber.font-size = #-1 } }
  \midi { }
}
