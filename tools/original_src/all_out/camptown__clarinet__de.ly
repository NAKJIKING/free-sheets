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
  title = \markup { \fontsize #3 \bold "Camptown Races" }
  subtitle = \markup { \fontsize #0 "Volkslied von Foster" }
  composer = "Stephen Foster"
  arranger = \markup { \fontsize #-1 "Einfache Melodie — My Sheet Music" }
  subsubtitle = \markup { \fontsize #0.5 \bold "Klarinette in B" }
  tagline = ##f
}
melody = \absolute {
  \clef treble \transposition bes \key c \major \time 2/4 \tempo 4 = 120
  
  g'4 g'4 | g'4 e'4 | g'4 a'4 | g'4 e'4~ | e'4 e'4 | d'2~ | d'4 e'4 | d'2 | g'4 g'4 | g'4 e'4 | g'4 a'4 | g'4 e'4~ | e'4 d'4~ | d'4 e'4 | d'4 c'4~ | c'2 | \bar "|."
}
\score {
  <<
    \new Staff \with { \override VerticalAxisGroup.staff-staff-spacing.padding = #5 } { \melody }
  >>
  \layout { \context { \Score \override BarNumber.font-size = #-1 } }
  \midi { }
}
