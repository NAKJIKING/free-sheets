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
  title = \markup { \fontsize #3 \bold "Song without Words" }
  subtitle = \markup { \fontsize #0 "무언가 (스핀들러) · Song without Words" }
  composer = "Fritz Spindler"
  arranger = \markup { \fontsize #-1 "초급 단선율 · 내 악보함" }
  subsubtitle = \markup { \fontsize #0.5 \bold "바이올린" }
  tagline = ##f
}
melody = \absolute {
  \clef treble  \key c \major \time 3/8 \tempo 4 = 90
  
  a'4. | c''4. | e''4.~ | e''8 d''8 c''8 | b'4. | d''8 c''8 b'8 | a'4.~ | a'4 r8 | r4. | a'4. | c''4. | e''4. | a''4. | aes''4. | aes''8 fis''8 aes''8 | a''4. | \bar "|."
}
\score {
  <<
    \new Staff \with { \override VerticalAxisGroup.staff-staff-spacing.padding = #5 } { \melody }
  >>
  \layout { \context { \Score \override BarNumber.font-size = #-1 } }
  \midi { }
}
