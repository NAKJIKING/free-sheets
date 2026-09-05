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
  subsubtitle = \markup { \fontsize #0.5 \bold "Trompette si♭" }
  tagline = ##f
}
melody = \absolute {
  \clef treble \transposition bes \key g \major \time 3/4 \tempo 4 = 60
  
  g'8 g'16 a'16 b'8 a'16 b'16 c''16 b'16 a'16 g'16 | a'8 a'16 b'16 g'8 fis'16 e'16 fis'8 d'8 | b4 e'4 d'4 | c'8 d'16 e'16 c'8 b16 a16 b8 g8 | b8 c'16 d'16 e'8 e'8 d'4 | c'8 d'16 e'16 c'8 b16 a16 b8 g8 | g'8 g'16 fis'16 e'8 d'8 c'8 b8 | a16 c'16 b8 g2 | \bar "|."
}
\score {
  <<
    \new Staff \with { \override VerticalAxisGroup.staff-staff-spacing.padding = #5 } { \melody }
  >>
  \layout { \context { \Score \override BarNumber.font-size = #-1 } }
  \midi { }
}
