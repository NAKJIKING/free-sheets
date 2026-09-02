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
  title = \markup { \fontsize #3 \bold "뮤제트 D장조" }
  subtitle = \markup { \fontsize #0 "Musette in D major BWV Anh.126 (안나 막달레나 바흐 소곡집)" }
  composer = "작자 미상 · 바흐 소곡집 수록 (J. S. Bach 편, 1685–1750)"
  arranger = "단선율 초급판 · 내 악보함"
  tagline = ##f
}
melody = \absolute {
  \key d \major \time 2/4 \tempo 4 = 100
  
  a''4 g''16 fis''16 e''16 d''16 | a''4 g''16 fis''16 e''16 d''16 | fis'16 g'16 a'8 g'8 fis'8 | e'8 a'8 fis'8 d'8 | a''4 g''16 fis''16 e''16 d''16 | a''4 g''16 fis''16 e''16 d''16 | fis'16 g'16 a'8 g'8 fis'8 | e'8 a'8 d'4 | cis''16 d''16 e''8 cis''16 d''16 e''8 | a''8 e''8 e''4 | a''8 e''8 a''8 e''8 | d''16 cis''16 b'16 a'16 b'8 e'8 | e''8 dis''8 e'8 d''8~ | d''8 cis''8 a''8 gis''8 | e''8 dis''8 e'8 d''8~ | d''8 cis''8 a''8 gis''8 | e''16 dis''16 cis''16 dis''16 e''16 dis''16 cis''16 dis''16 | e''8 gis'8 a'8 d''8 | cis''16 d''16 e''8 a'8 d'8 | cis'16 d'16 e'8 a4 | \bar "|."
}
\score {
  <<
    \new Staff \with { \override VerticalAxisGroup.staff-staff-spacing.padding = #5 } { \melody }
    \addlyrics { 라 솔 파♯ 미 레 라 솔 파♯ 미 레 파♯ 솔 라 솔 파♯ 미 라 파♯ 레 라 솔 파♯ 미 레 라 솔 파♯ 미 레 파♯ 솔 라 솔 파♯ 미 라 레 도♯ 레 미 도♯ 레 미 라 미 미 라 미 라 미 레 도♯ 시 라 시 미 미 레♯ 미 레 도♯ 라 솔♯ 미 레♯ 미 레 도♯ 라 솔♯ 미 레♯ 도♯ 레♯ 미 레♯ 도♯ 레♯ 미 솔♯ 라 레 도♯ 레 미 라 레 도♯ 레 미 라 }
  >>
  \layout { \context { \Score \override BarNumber.font-size = #-1 } }
  \midi { }
}
