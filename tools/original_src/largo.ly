\version "2.24.4"
#(set-global-staff-size 24)
\paper {
  #(set-paper-size "a4")
  top-margin = 16\mm  bottom-margin = 14\mm
  left-margin = 16\mm right-margin = 16\mm
  ragged-bottom = ##t  ragged-last-bottom = ##t
  property-defaults.fonts.roman = "Nanum Gothic"
  oddFooterMarkup = \markup { \fill-line { \fontsize #-3 \line { "" } } }
  evenFooterMarkup = \markup { \fill-line { \fontsize #-3 \line { "" } } }
}
\header {
  title = \markup { \fontsize #3 \bold "꿈속의 고향 (신세계 교향곡 라르고)" }
  subtitle = \markup { \fontsize #0 "Largo — 교향곡 9번 '신세계로부터' Op.95 2악장 주제 (Goin' Home)" }
  composer = "안토닌 드보르자크 (Antonín Dvořák, 1841–1904)"
  arranger = "단선율 초급판 · 내 악보함"
  tagline = ##f
}
melody = \absolute {
  \key c \major \time 4/4 \tempo 4 = 60
  
  e'8. g'16 g'4 e'8. d'16 c'4 | d'8. e'16 g'8. e'16 d'2 | e'8. g'16 g'4 e'8. d'16 c'4 | d'8 e'8 d'8. c'16 c'2 | a'8. c''16 c''4 b'8 g'8 a'4 | a'8 c''8 b'8 g'8 a'2 | a'8. c''16 c''4 b'8 g'8 a'4 | a'8 c''8 b'8 g'8 a'2 | e'8. g'16 g'4 e'8 d'8 c'4 | d'8. e'16 g'8. e'16 d'2 | e'8. g'16 g'4 c''8. d''16 e''4 | d''8. c''16 d''8 a'8 c''2 | \bar "|."
}
\score {
  <<
    \new Staff \with { \override VerticalAxisGroup.staff-staff-spacing.padding = #5 } { \melody }
    \addlyrics { 미 솔 솔 미 레 도 레 미 솔 미 레 미 솔 솔 미 레 도 레 미 레 도 도 라 도 도 시 솔 라 라 도 시 솔 라 라 도 도 시 솔 라 라 도 시 솔 라 미 솔 솔 미 레 도 레 미 솔 미 레 미 솔 솔 도 레 미 레 도 레 라 도 }
  >>
  \layout { \context { \Score \override BarNumber.font-size = #-1 } }
  \midi { }
}
