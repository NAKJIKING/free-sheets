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
  title = \markup { \fontsize #1 \bold "Polonaise in F major, BWV Anh.117a" }
  subtitle = \markup { \fontsize #0 "Polonaise en fa majeur, BWV Anh.117a · mélodie" }
  composer = "Johann Sebastian Bach"
  arranger = \markup { \fontsize #-1 "Mélodie facile — My Sheet Music" }
  subsubtitle = \markup { \fontsize #0.5 \bold "Flûte" }
  tagline = ##f
}
melody = \absolute {
  \clef treble  \key f \major \time 3/4 \tempo 4 = 60
  
  f''8 f''16 g''16 a''8 g''16 a''16 bes''16 a''16 g''16 f''16 | g''8 g''16 a''16 f''8 e''16 d''16 e''8 c''8 | a'4 d''4 c''4 | bes'8 c''16 d''16 bes'8 a'16 g'16 a'8 f'8 | a'8 bes'16 c''16 d''8 d''8 c''4 | bes'8 c''16 d''16 bes'8 a'16 g'16 a'8 f'8 | f''8 f''16 e''16 d''8 c''8 bes'8 a'8 | g'16 bes'16 a'8 f'2 | \bar "|."
}
\score {
  <<
    \new Staff \with { \override VerticalAxisGroup.staff-staff-spacing.padding = #5 } { \melody }
  >>
  \layout { \context { \Score \override BarNumber.font-size = #-1 } }
  \midi { }
}
