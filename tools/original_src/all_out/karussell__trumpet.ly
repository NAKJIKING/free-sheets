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
  title = \markup { \fontsize #3 \bold "Karussell-Walzer" }
  subtitle = \markup { \fontsize #0 "회전목마 왈츠 · Karussell-Walzer" }
  composer = "Ludwig Streabbog"
  arranger = \markup { \fontsize #-1 "초급 단선율 · 내 악보함" }
  subsubtitle = \markup { \fontsize #0.5 \bold "트럼펫 (B♭)" }
  tagline = ##f
}
melody = \absolute {
  \clef treble \transposition bes \key c \major \time 3/4 \tempo 4 = 120
  
  e'2 f'4 | g'2 c'4 | b2.~ | b2. | f'2 g'4 | a'2 d'4 | c'2.~ | c'2. | \bar "|."
}
\score {
  <<
    \new Staff \with { \override VerticalAxisGroup.staff-staff-spacing.padding = #5 } { \melody }
  >>
  \layout { \context { \Score \override BarNumber.font-size = #-1 } }
  \midi { }
}
