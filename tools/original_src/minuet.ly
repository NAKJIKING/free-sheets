\version "2.24.4"
#(set-global-staff-size 22)
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
  title = \markup { \fontsize #3 \bold "미뉴에트 G장조" }
  subtitle = \markup { \fontsize #0 "Minuet in G major BWV Anh.114 (안나 막달레나 바흐 소곡집)" }
  composer = "크리스티안 페촐트 (Christian Petzold, 1677–1733)"
  arranger = "단선율 초급판 · 내 악보함"
  tagline = ##f
}
melody = \absolute {
  \key g \major \time 3/4 \tempo 4 = 112
  
  d''4 g'8 a'8 b'8 c''8 | d''4 g'4 g'4 | e''4 c''8 d''8 e''8 fis''8 | g''4 g'4 g'4 | c''4 d''8 c''8 b'8 a'8 | b'4 c''8 b'8 a'8 g'8 | fis'4 g'8 a'8 b'8 g'8 | a'2. | d''4 g'8 a'8 b'8 c''8 | d''4 g'4 g'4 | e''4 c''8 d''8 e''8 fis''8 | g''4 g'4 g'4 | c''4 d''8 c''8 b'8 a'8 | b'4 c''8 b'8 a'8 g'8 | a'4 b'8 a'8 g'8 fis'8 | g'2. | b''4 g''8 a''8 b''8 g''8 | a''4 d''8 e''8 fis''8 d''8 | g''4 e''8 fis''8 g''8 d''8 | cis''4 b'8 cis''8 a'4 | a'8 b'8 cis''8 d''8 e''8 fis''8 | g''4 fis''4 e''4 | fis''4 a'4 cis''4 | d''2. | d''4 g'8 fis'8 g'4 | e''4 g'8 fis'8 g'4 | d''4 c''4 b'4 | a'8 g'8 fis'8 g'8 a'4 | d'8 e'8 fis'8 g'8 a'8 b'8 | c''4 b'4 a'4 | b'8 d''8 g'4 fis'4 | g'2. | \bar "|."
}
\score {
  <<
    \new Staff \with { \override VerticalAxisGroup.staff-staff-spacing.padding = #5 } { \melody }
    \addlyrics { 레 솔 라 시 도 레 솔 솔 미 도 레 미 파♯ 솔 솔 솔 도 레 도 시 라 시 도 시 라 솔 파♯ 솔 라 시 솔 라 레 솔 라 시 도 레 솔 솔 미 도 레 미 파♯ 솔 솔 솔 도 레 도 시 라 시 도 시 라 솔 라 시 라 솔 파♯ 솔 시 솔 라 시 솔 라 레 미 파♯ 레 솔 미 파♯ 솔 레 도♯ 시 도♯ 라 라 시 도♯ 레 미 파♯ 솔 파♯ 미 파♯ 라 도♯ 레 레 솔 파♯ 솔 미 솔 파♯ 솔 레 도 시 라 솔 파♯ 솔 라 레 미 파♯ 솔 라 시 도 시 라 시 레 솔 파♯ 솔 }
  >>
  \layout { \context { \Score \override BarNumber.font-size = #-1 } }
  \midi { }
}
