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
  title = \markup { \fontsize #1 \bold "Polonaise in F major, BWV Anh.117a" }
  subtitle = \markup { \fontsize #0 "Polonaise in F major, BWV Anh.117a" }
  composer = "Johann Sebastian Bach"
  arranger = \markup { \fontsize #-1 "Easy melody — My Sheet Music" }
  subsubtitle = \markup { \fontsize #0.5 \bold "Cello" }
  tagline = ##f
}
melody = \absolute {
  \clef bass  \key f \major \time 3/4 \tempo 4 = 60
  
  f8 f16 g16 a8 g16 a16 bes16 a16 g16 f16 | g8 g16 a16 f8 e16 d16 e8 c8 | a,4 d4 c4 | bes,8 c16 d16 bes,8 a,16 g,16 a,8 f,8 | a,8 bes,16 c16 d8 d8 c4 | bes,8 c16 d16 bes,8 a,16 g,16 a,8 f,8 | f8 f16 e16 d8 c8 bes,8 a,8 | g,16 bes,16 a,8 f,2 | \bar "|."
}
\score {
  <<
    \new Staff \with { \override VerticalAxisGroup.staff-staff-spacing.padding = #5 } { \melody }
  >>
  \layout { \context { \Score \override BarNumber.font-size = #-1 } }
  \midi { }
}
