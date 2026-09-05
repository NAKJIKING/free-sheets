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
  title = \markup { \fontsize #3 \bold "My Old Kentucky Home" }
  subtitle = \markup { \fontsize #0 "Mi viejo hogar de Kentucky · canción de Foster" }
  composer = "Stephen Foster"
  arranger = \markup { \fontsize #-1 "Melodía fácil — My Sheet Music" }
  subsubtitle = \markup { \fontsize #0.5 \bold "Piano" }
  tagline = ##f
}
melody = \absolute {
  \clef treble  \key c \major \time 4/4 \tempo 4 = 56
  
  e''8 e''4 e''4 c''4 d''8 | e''8 f''8 e''8 f''8 a''8 g''4. | f''8 e''8 d''4 c''8 c''8 b'4 | c''8 d''2. d''8 | d''8 e''4 e''4 c''4 d''8 | e''8 f''8 e''8 f''8 a''8 g''4 c''8 | d''8 e''4 e''4 d''8 c''8 e''8 | d''8 c''2.~ c''8~ | c''8 g''4. e''8 f''4. | a''8 g''8 e''2~ e''8 d''8~ | d''8 c''4. d''8 c''4. | a'8 c''4 f'4 e'4 c''8 | d''8 e''4 e''4 c''4 d''8 | e''8 f''8 e''8 f''8 a''8 g''4 c''8 | d''8 e''8 c''8 f''8 e''8 d''4 d''8 | b'8 c''4 f'4 e'4. | \bar "|."
}
\score {
  <<
    \new Staff \with { \override VerticalAxisGroup.staff-staff-spacing.padding = #5 } { \melody }
  >>
  \layout { \context { \Score \override BarNumber.font-size = #-1 } }
  \midi { }
}
