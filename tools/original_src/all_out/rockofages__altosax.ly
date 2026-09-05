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
  title = \markup { \fontsize #3 \bold "Rock of Ages" }
  subtitle = \markup { \fontsize #0 "만세 반석 열리니 · Rock of Ages" }
  composer = "Thomas Hastings"
  arranger = \markup { \fontsize #-1 "초급 단선율 · 내 악보함" }
  subsubtitle = \markup { \fontsize #0.5 \bold "알토색소폰 (E♭)" }
  tagline = ##f
}
melody = \absolute {
  \clef treble \transposition ees \key c \major \time 6/4 \tempo 4 = 120
  
  g'4. a'8 g'2 e'2 | c''4. a'8 g'1 | c''4. d''8 e''2. d''4 | c''4 b'4 c''1 | b'4. c''8 d''2. d''4 | b'4 g'4 c''1 | b'4. c''8 d''2. d''4 | b'4 g'4 c''1 | g'4. a'8 g'2 e'2 | c''4. a'8 g'1 | c''4. d''8 e''2. d''4 | c''4 b'4 c''1 | \bar "|."
}
\score {
  <<
    \new Staff \with { \override VerticalAxisGroup.staff-staff-spacing.padding = #5 } { \melody }
  >>
  \layout { \context { \Score \override BarNumber.font-size = #-1 } }
  \midi { }
}
