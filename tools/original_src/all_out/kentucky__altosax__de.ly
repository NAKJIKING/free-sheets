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
  subtitle = \markup { \fontsize #0 "Mein altes Kentucky-Heim · Volkslied von Foster" }
  composer = "Stephen Foster"
  arranger = \markup { \fontsize #-1 "Einfache Melodie — My Sheet Music" }
  subsubtitle = \markup { \fontsize #0.5 \bold "Altsaxophon in Es" }
  tagline = ##f
}
melody = \absolute {
  \clef treble \transposition ees \key bes \major \time 4/4 \tempo 4 = 56
  
  d''8 d''4 d''4 bes'4 c''8 | d''8 ees''8 d''8 ees''8 g''8 f''4. | ees''8 d''8 c''4 bes'8 bes'8 a'4 | bes'8 c''2. c''8 | c''8 d''4 d''4 bes'4 c''8 | d''8 ees''8 d''8 ees''8 g''8 f''4 bes'8 | c''8 d''4 d''4 c''8 bes'8 d''8 | c''8 bes'2.~ bes'8~ | bes'8 f''4. d''8 ees''4. | g''8 f''8 d''2~ d''8 c''8~ | c''8 bes'4. c''8 bes'4. | g'8 bes'4 ees'4 d'4 bes'8 | c''8 d''4 d''4 bes'4 c''8 | d''8 ees''8 d''8 ees''8 g''8 f''4 bes'8 | c''8 d''8 bes'8 ees''8 d''8 c''4 c''8 | a'8 bes'4 ees'4 d'4. | \bar "|."
}
\score {
  <<
    \new Staff \with { \override VerticalAxisGroup.staff-staff-spacing.padding = #5 } { \melody }
  >>
  \layout { \context { \Score \override BarNumber.font-size = #-1 } }
  \midi { }
}
