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
  title = \markup { \fontsize #3 \bold "즐거운 농부" }
  subtitle = \markup { \fontsize #0 "Fröhlicher Landmann — 유겐트 앨범 Op.68 No.10 (왼손 선율)" }
  composer = "로베르트 슈만 (Robert Schumann, 1810–1856)"
  arranger = "단선율 초급판 · 내 악보함"
  tagline = ##f
}
melody = \absolute {
  \key f \major \time 4/4 \tempo 4 = 108
  \partial 8
  c'8 | f'4. a'8 c''4. f'8 | bes'8 d''8 f''8 d''8 c''4. a'8 | bes'8 g'8 c'8 bes'8 a'8 f'8 c'8 a'8 | e'4 d'4 c'4. c'8 | f'4. a'8 c''4. f'8 | bes'8 d''8 f''8 d''8 c''4. a'8 | bes'8 g'8 c'8 bes'8 a'8 f'8 c'8 a'8 | e'4 d'4 c'4. c'8 | g'4. f'8 e'4. c'8 | g'8 f'8 e'8 d'8 e'4. c'8 | f'4. a'8 c''4. f'8 | bes'8 d''8 f''8 d''8 c''4. a'8 | bes'8 g'8 c'8 bes'8 a'8 f'8 c'8 a'8 | g'4 e'4 f'4. c'8 | g'4. f'8 e'4. c'8 | g'8 f'8 e'8 d'8 e'4. c'8 | f'4. a'8 c''4. f'8 | bes'8 d''8 f''8 d''8 c''4. a'8 | bes'8 g'8 c'8 bes'8 a'8 f'8 c'8 a'8 | g'4 e'4 f'2 | \bar "|."
}
\score {
  <<
    \new Staff \with { \override VerticalAxisGroup.staff-staff-spacing.padding = #5 } { \melody }
    \addlyrics { 도 파 라 도 파 시♭ 레 파 레 도 라 시♭ 솔 도 시♭ 라 파 도 라 미 레 도 도 파 라 도 파 시♭ 레 파 레 도 라 시♭ 솔 도 시♭ 라 파 도 라 미 레 도 도 솔 파 미 도 솔 파 미 레 미 도 파 라 도 파 시♭ 레 파 레 도 라 시♭ 솔 도 시♭ 라 파 도 라 솔 미 파 도 솔 파 미 도 솔 파 미 레 미 도 파 라 도 파 시♭ 레 파 레 도 라 시♭ 솔 도 시♭ 라 파 도 라 솔 미 파 }
  >>
  \layout { \context { \Score \override BarNumber.font-size = #-1 } }
  \midi { }
}
