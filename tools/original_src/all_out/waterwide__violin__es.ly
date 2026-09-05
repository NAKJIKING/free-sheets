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
  title = \markup { \fontsize #3 \bold "The Water Is Wide" }
  subtitle = \markup { \fontsize #0 "canción tradicional" }
  composer = "Traditional"
  arranger = \markup { \fontsize #-1 "Melodía fácil — My Sheet Music" }
  subsubtitle = \markup { \fontsize #0.5 \bold "Violín" }
  tagline = ##f
}
melody = \absolute {
  \clef treble  \key c \major \time 3/4 \tempo 4 = 120
  
  g'4 c''4 c''8 d''8 | e''2 d''8 d''8 | c''4 a'4 g'4~ | g'4 g'4 c''4 | b'4 c''2~ | c''4 d''4 e''4 | f''8 e''8 d''2~ | d''2. | \bar "|."
}
\score {
  <<
    \new Staff \with { \override VerticalAxisGroup.staff-staff-spacing.padding = #5 } { \melody }
  >>
  \layout { \context { \Score \override BarNumber.font-size = #-1 } }
  \midi { }
}
