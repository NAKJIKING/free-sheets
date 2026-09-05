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
  title = \markup { \fontsize #3 \bold "Song without Words" }
  subtitle = \markup { \fontsize #0 "Canción sin palabras · melodía" }
  composer = "Fritz Spindler"
  arranger = \markup { \fontsize #-1 "Melodía fácil — My Sheet Music" }
  subsubtitle = \markup { \fontsize #0.5 \bold "Violonchelo" }
  tagline = ##f
}
melody = \absolute {
  \clef bass  \key c \major \time 3/8 \tempo 4 = 90
  
  a,4. | c4. | e4.~ | e8 d8 c8 | b,4. | d8 c8 b,8 | a,4.~ | a,4 r8 | r4. | a,4. | c4. | e4. | a4. | aes4. | aes8 fis8 aes8 | a4. | \bar "|."
}
\score {
  <<
    \new Staff \with { \override VerticalAxisGroup.staff-staff-spacing.padding = #5 } { \melody }
  >>
  \layout { \context { \Score \override BarNumber.font-size = #-1 } }
  \midi { }
}
