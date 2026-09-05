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
  title = \markup { \fontsize #1 \bold "100 Progressive Studies, Op.139 No.2" }
  subtitle = \markup { \fontsize #0 "100 estudios progresivos, op.139 No.2 · melodía" }
  composer = "Carl Czerny"
  arranger = \markup { \fontsize #-1 "Melodía fácil — My Sheet Music" }
  subsubtitle = \markup { \fontsize #0.5 \bold "Flauta dulce" }
  tagline = ##f
}
melody = \absolute {
  \clef treble \transposition c'' \key c \major \time 4/4 \tempo 4 = 120
  
  e''4 e''4 g''4 e''4 | c''4 c''4 e''4 c''4 | d''4 d''4 f''4 d''4 | e''4 e''4 e''4 e''4 | e''4 e''4 g''4 e''4 | c''4 c''4 e''4 c''4 | d''4 f''4 e''4 d''4 | c''4 e''4 c''2 | e''4 e''4 g''4 e''4 | c''4 c''4 e''4 c''4 | d''4 d''4 f''4 d''4 | e''4 e''4 e''4 e''4 | e''4 e''4 g''4 e''4 | c''4 c''4 e''4 c''4 | d''4 f''4 e''4 d''4 | c''4 e''4 c''2 | \bar "|."
}
\score {
  <<
    \new Staff \with { \override VerticalAxisGroup.staff-staff-spacing.padding = #5 } { \melody }
  >>
  \layout { \context { \Score \override BarNumber.font-size = #-1 } }
  \midi { }
}
