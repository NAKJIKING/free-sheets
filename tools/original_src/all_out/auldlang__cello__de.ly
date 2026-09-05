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
  title = \markup { \fontsize #3 \bold "Auld Lang Syne" }
  subtitle = \markup { \fontsize #0 "Nehmt Abschied, Brüder" }
  composer = "Traditional"
  arranger = \markup { \fontsize #-1 "Einfache Melodie — My Sheet Music" }
  subsubtitle = \markup { \fontsize #0.5 \bold "Violoncello" }
  tagline = ##f
}
melody = \absolute {
  \clef bass  \key c \major \time 4/4 \tempo 4 = 120
  
  g,4 c4. b,8 c4 | e4 d4. c8 d4 | e8 d8 c4. c8 e4 | g4 a2. | a1 | \bar "|."
}
\score {
  <<
    \new Staff \with { \override VerticalAxisGroup.staff-staff-spacing.padding = #5 } { \melody }
  >>
  \layout { \context { \Score \override BarNumber.font-size = #-1 } }
  \midi { }
}
