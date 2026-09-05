\version "2.24.4"
#(set-global-staff-size 24)
\paper {
  #(set-paper-size "a4")
  top-margin = 16\mm  bottom-margin = 14\mm
  left-margin = 16\mm right-margin = 16\mm
  ragged-bottom = ##t  ragged-last-bottom = ##t
  #(define fonts (set-global-fonts #:roman "WenQuanYi Zen Hei" #:sans "WenQuanYi Zen Hei" #:factor (/ staff-height pt 20)))
  oddFooterMarkup = \markup { \fill-line { \fontsize #-3 \line { "" } } }
  evenFooterMarkup = \markup { \fill-line { \fontsize #-3 \line { "" } } }
}
\header {
  title = \markup { \fontsize #3 \bold "Can-Can — Galop infernal" }
  subtitle = \markup { \fontsize #0 "康康舞 · 《地狱中的奥菲欧》加洛普" }
  composer = "Jacques Offenbach"
  arranger = \markup { \fontsize #-1 "简易旋律 — My Sheet Music" }
  subsubtitle = \markup { \fontsize #0.5 \bold "吉他" }
  tagline = ##f
}
melody = \absolute {
  \clef "treble_8" \transposition c \key aes \major \time 2/4 \tempo 4 = 112
  
  ees''8 f''8 c''8 des''8 | bes'4 bes'4 | bes'8 des''8 c''8 bes'8 | aes'8 aes''8 g''8 f''8 | ees''8 des''8 c''8 bes'8 | aes'2 | bes'8 des''8 c''8 bes'8 | ees''4 ees''4 | ees''8 f''8 c''8 des''8 | bes'4 bes'4 | bes'8 des''8 c''8 bes'8 | aes'8 ees''8 bes'8 c''8 | aes'4 ees'4 | aes'2 | bes'8 des''8 c''8 bes'8 | ees''4 ees''4 | \bar "|."
}
\score {
  <<
    \new Staff \with { \override VerticalAxisGroup.staff-staff-spacing.padding = #5 } { \melody }
  >>
  \layout { \context { \Score \override BarNumber.font-size = #-1 } }
  \midi { }
}
