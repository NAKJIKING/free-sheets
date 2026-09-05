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
  subsubtitle = \markup { \fontsize #0.5 \bold "中音萨克斯 (降E)" }
  tagline = ##f
}
melody = \absolute {
  \clef treble \transposition ees \key f \major \time 2/4 \tempo 4 = 112
  
  c''8 d''8 a'8 bes'8 | g'4 g'4 | g'8 bes'8 a'8 g'8 | f'8 f''8 e''8 d''8 | c''8 bes'8 a'8 g'8 | f'2 | g'8 bes'8 a'8 g'8 | c''4 c''4 | c''8 d''8 a'8 bes'8 | g'4 g'4 | g'8 bes'8 a'8 g'8 | f'8 c''8 g'8 a'8 | f'4 c'4 | f'2 | g'8 bes'8 a'8 g'8 | c''4 c''4 | \bar "|."
}
\score {
  <<
    \new Staff \with { \override VerticalAxisGroup.staff-staff-spacing.padding = #5 } { \melody }
  >>
  \layout { \context { \Score \override BarNumber.font-size = #-1 } }
  \midi { }
}
