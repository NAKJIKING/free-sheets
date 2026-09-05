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
  title = \markup { \fontsize #3 \bold "Can-Can — Galop infernal" }
  subtitle = \markup { \fontsize #0 "캉캉 (천국과 지옥) · Can-Can — Galop infernal" }
  composer = "Jacques Offenbach"
  arranger = \markup { \fontsize #-1 "초급 단선율 · 내 악보함" }
  subsubtitle = \markup { \fontsize #0.5 \bold "플루트" }
  tagline = ##f
}
melody = \absolute {
  \clef treble  \key c \major \time 2/4 \tempo 4 = 112
  
  g''8 a''8 e''8 f''8 | d''4 d''4 | d''8 f''8 e''8 d''8 | c''8 c'''8 b''8 a''8 | g''8 f''8 e''8 d''8 | c''2 | d''8 f''8 e''8 d''8 | g''4 g''4 | g''8 a''8 e''8 f''8 | d''4 d''4 | d''8 f''8 e''8 d''8 | c''8 g''8 d''8 e''8 | c''4 g'4 | c''2 | d''8 f''8 e''8 d''8 | g''4 g''4 | \bar "|."
}
\score {
  <<
    \new Staff \with { \override VerticalAxisGroup.staff-staff-spacing.padding = #5 } { \melody }
  >>
  \layout { \context { \Score \override BarNumber.font-size = #-1 } }
  \midi { }
}
