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
  title = \markup { \fontsize #1 \bold "Vorschule im Klavierspiel, Op.101" }
  subtitle = \markup { \fontsize #0 "拜厄鋼琴基本教程 作品101 · 旋律" }
  composer = "Ferdinand Beyer"
  arranger = \markup { \fontsize #-1 "简易旋律 — My Sheet Music" }
  subsubtitle = \markup { \fontsize #0.5 \bold "钢琴" }
  tagline = ##f
}
melody = \absolute {
  \clef treble  \key c \major \time 4/4 \tempo 4 = 114
  
  g'1 | d''2 c''2 | b'4 d''4 c''4 b'4 | a'1 | g'1 | d''2 c''2 | b'4 d''4 c''4 a'4 | g'1 | a'1 | g'4 d''4 c''4 b'4 | a'1 | d''4 g'4 b'4 a'4 | g'1 | d''2 c''2 | b'4 d''4 c''4 a'4 | g'1 | \bar "|."
}
\score {
  <<
    \new Staff \with { \override VerticalAxisGroup.staff-staff-spacing.padding = #5 } { \melody }
  >>
  \layout { \context { \Score \override BarNumber.font-size = #-1 } }
  \midi { }
}
