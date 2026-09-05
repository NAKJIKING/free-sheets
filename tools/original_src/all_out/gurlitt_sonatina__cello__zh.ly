\version "2.24.4"
#(set-global-staff-size 24)
\paper {
  #(set-paper-size "a4")
  top-margin = 16\mm  bottom-margin = 14\mm
  left-margin = 16\mm right-margin = 16\mm
  ragged-bottom = ##t  ragged-last-bottom = ##t
  #(define fonts (set-global-fonts #:roman "WenQuanYi Zen Hei" #:sans "WenQuanYi Zen Hei" #:factor (/ staff-height pt 20)))
  oddFooterMarkup = \markup { \fill-line { \fontsize #-3 \line { "" } } }
  evenFooterMarkup = \markup { \fill-line { \fontsize #-3 \line { "" } } }
}
\header {
  title = \markup { \fontsize #3 \bold "Sonatina" }
  subtitle = \markup { \fontsize #0 "小奏鳴曲 · 旋律" }
  composer = "Cornelius Gurlitt"
  arranger = \markup { \fontsize #-1 "简易旋律 — My Sheet Music" }
  subsubtitle = \markup { \fontsize #0.5 \bold "大提琴" }
  tagline = ##f
}
melody = \absolute {
  \clef bass  \key c \major \time 4/4 \tempo 4 = 120
  
  c4 e4 d4 f4 | e4 g4 c4 d8 e8 | f4 e4 d4 e8 f8 | g4 e4 c2 | c4 e4 d4 f4 | e4 g4 c4 d8 e8 | f4 e4 d4 e8 f8 | g4 e4 c2 | \bar "|."
}
\score {
  <<
    \new Staff \with { \override VerticalAxisGroup.staff-staff-spacing.padding = #5 } { \melody }
  >>
  \layout { \context { \Score \override BarNumber.font-size = #-1 } }
  \midi { }
}
