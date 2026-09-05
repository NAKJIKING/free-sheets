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
  title = \markup { \fontsize #3 \bold "Rondo in C major" }
  subtitle = \markup { \fontsize #0 "Rondo dalam C mayor · melodi mudah" }
  composer = "Ludwig van Beethoven"
  arranger = \markup { \fontsize #-1 "Melodi mudah — My Sheet Music" }
  subsubtitle = \markup { \fontsize #0.5 \bold "Piano" }
  tagline = ##f
}
melody = \absolute {
  \clef treble  \key c \major \time 4/4 \tempo 4 = 120
  
  r2. e'4 | g'1 | f'4 a'2 g'8 f'8 | e'4 g'2 f'8 e'8 | d'8 e'8 f'8 e'8 g'8 f'8 e'8 d'8 | r1 | r2. e'4 | g'1 | f'2~ f'8 a'8 g'8 f'8 | e'8 g'8 f'8 e'8 d'8 f'8 e'8 d'8 | r2 e'4 d'4 | r1 | r2. e'4 | f'4 d'2. | \bar "|."
}
\score {
  <<
    \new Staff \with { \override VerticalAxisGroup.staff-staff-spacing.padding = #5 } { \melody }
  >>
  \layout { \context { \Score \override BarNumber.font-size = #-1 } }
  \midi { }
}
