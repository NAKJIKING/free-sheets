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
  title = \markup { \fontsize #3 \bold "Joy to the World" }
  subtitle = \markup { \fontsize #0 "普世歡騰 · 聖誕頌歌" }
  composer = "Lowell Mason after Handel"
  arranger = \markup { \fontsize #-1 "简易旋律 — My Sheet Music" }
  subsubtitle = \markup { \fontsize #0.5 \bold "大提琴" }
  tagline = ##f
}
melody = \absolute {
  \clef bass  \key c \major \time 4/4 \tempo 4 = 132
  
  c'2 b4. a8 | g2. f4 | e2 d2 | c2. g4 | a2. a4 | b2. b4 | c'1~ | c'2. c'4 | c'4 b4 a4 g4 | g4. f8 e4 c'4 | c'4 b4 a4 g4 | g4. f8 e4 e4 | e4 e4 e4 e8 f8 | g2. f8 e8 | d4 d4 d4 d8 e8 | f2. e8 d8 | \bar "|."
}
\score {
  <<
    \new Staff \with { \override VerticalAxisGroup.staff-staff-spacing.padding = #5 } { \melody }
  >>
  \layout { \context { \Score \override BarNumber.font-size = #-1 } }
  \midi { }
}
