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
  title = \markup { \fontsize #3 \bold "Gymnopédie No.2" }
  subtitle = \markup { \fontsize #0 "裸體歌舞 第2號 · 旋律" }
  composer = "Erik Satie"
  arranger = \markup { \fontsize #-1 "简易旋律 — My Sheet Music" }
  subsubtitle = \markup { \fontsize #0.5 \bold "小号 (降B)" }
  tagline = ##f
}
melody = \absolute {
  \clef treble \transposition bes \key a \minor \time 3/4 \tempo 4 = 60
  
  r4 g2~ | g4 a2~ | a4 g2~ | g4 a2 | g'4 g2 | a'4 g'4 f'4 | e'4 f'4 g'4 | d'4 a2 | \bar "|."
}
\score {
  <<
    \new Staff \with { \override VerticalAxisGroup.staff-staff-spacing.padding = #5 } { \melody }
  >>
  \layout { \context { \Score \override BarNumber.font-size = #-1 } }
  \midi { }
}
