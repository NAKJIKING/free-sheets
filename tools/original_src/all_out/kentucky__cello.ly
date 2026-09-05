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
  title = \markup { \fontsize #3 \bold "My Old Kentucky Home" }
  subtitle = \markup { \fontsize #0 "켄터키 옛집 · My Old Kentucky Home" }
  composer = "Stephen Foster"
  arranger = \markup { \fontsize #-1 "초급 단선율 · 내 악보함" }
  subsubtitle = \markup { \fontsize #0.5 \bold "첼로" }
  tagline = ##f
}
melody = \absolute {
  \clef bass  \key c \major \time 4/4 \tempo 4 = 56
  
  e8 e4 e4 c4 d8 | e8 f8 e8 f8 a8 g4. | f8 e8 d4 c8 c8 b,4 | c8 d2. d8 | d8 e4 e4 c4 d8 | e8 f8 e8 f8 a8 g4 c8 | d8 e4 e4 d8 c8 e8 | d8 c2.~ c8~ | c8 g4. e8 f4. | a8 g8 e2~ e8 d8~ | d8 c4. d8 c4. | a,8 c4 f,4 e,4 c8 | d8 e4 e4 c4 d8 | e8 f8 e8 f8 a8 g4 c8 | d8 e8 c8 f8 e8 d4 d8 | b,8 c4 f,4 e,4. | \bar "|."
}
\score {
  <<
    \new Staff \with { \override VerticalAxisGroup.staff-staff-spacing.padding = #5 } { \melody }
  >>
  \layout { \context { \Score \override BarNumber.font-size = #-1 } }
  \midi { }
}
