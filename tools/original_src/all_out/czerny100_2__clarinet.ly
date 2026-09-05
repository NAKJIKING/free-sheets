\version "2.24.4"
#(set-global-staff-size 24)
\paper {
  #(set-paper-size "a4")
  top-margin = 16\mm  bottom-margin = 14\mm
  left-margin = 16\mm right-margin = 16\mm
  ragged-bottom = ##t  ragged-last-bottom = ##t
  #(define fonts (set-global-fonts #:roman "Nanum Gothic" #:sans "Nanum Gothic" #:factor (/ staff-height pt 20)))
  oddFooterMarkup = \markup { \fill-line { \fontsize #-3 \line { "" } } }
  evenFooterMarkup = \markup { \fill-line { \fontsize #-3 \line { "" } } }
}
\header {
  title = \markup { \fontsize #2 \bold "100 Recreations, Op.139 No.2" }
  subtitle = \markup { \fontsize #0 "체르니 100번 소품 · 100 Recreations, Op.139 No.2" }
  composer = "Carl Czerny"
  arranger = \markup { \fontsize #-1 "초급 단선율 · 내 악보함" }
  subsubtitle = \markup { \fontsize #0.5 \bold "클라리넷 (B♭)" }
  tagline = ##f
}
melody = \absolute {
  \clef treble \transposition bes \key c \major \time 3/4 \tempo 4 = 120
  
  c'4 d'4 e'4 | e'4 e'4 e'4 | d'4 e'4 f'4 | f'4 f'4 f'4 | e'4 f'4 g'4 | g'4 g'4 g'4 | g'4 f'4 d'4 | c'2. | c'4 d'4 e'4 | e'4 e'4 e'4 | d'4 e'4 f'4 | f'4 f'4 f'4 | \bar "|."
}
\score {
  <<
    \new Staff \with { \override VerticalAxisGroup.staff-staff-spacing.padding = #5 } { \melody }
  >>
  \layout { \context { \Score \override BarNumber.font-size = #-1 } }
  \midi { }
}
