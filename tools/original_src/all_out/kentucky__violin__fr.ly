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
  subtitle = \markup { \fontsize #0 "chanson de Foster" }
  composer = "Stephen Foster"
  arranger = \markup { \fontsize #-1 "Mélodie facile — My Sheet Music" }
  subsubtitle = \markup { \fontsize #0.5 \bold "Violon" }
  tagline = ##f
}
melody = \absolute {
  \clef treble  \key g \major \time 4/4 \tempo 4 = 56
  
  b'8 b'4 b'4 g'4 a'8 | b'8 c''8 b'8 c''8 e''8 d''4. | c''8 b'8 a'4 g'8 g'8 fis'4 | g'8 a'2. a'8 | a'8 b'4 b'4 g'4 a'8 | b'8 c''8 b'8 c''8 e''8 d''4 g'8 | a'8 b'4 b'4 a'8 g'8 b'8 | a'8 g'2.~ g'8~ | g'8 d''4. b'8 c''4. | e''8 d''8 b'2~ b'8 a'8~ | a'8 g'4. a'8 g'4. | e'8 g'4 c'4 b4 g'8 | a'8 b'4 b'4 g'4 a'8 | b'8 c''8 b'8 c''8 e''8 d''4 g'8 | a'8 b'8 g'8 c''8 b'8 a'4 a'8 | fis'8 g'4 c'4 b4. | \bar "|."
}
\score {
  <<
    \new Staff \with { \override VerticalAxisGroup.staff-staff-spacing.padding = #5 } { \melody }
  >>
  \layout { \context { \Score \override BarNumber.font-size = #-1 } }
  \midi { }
}
