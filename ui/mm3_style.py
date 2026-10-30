#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Style général léger de MM3.

Ce proxy conserve le style natif de la plateforme et ne modifie que quelques
métriques d'ergonomie. Il évite ainsi le gros filtre QSS global qui avait déjà
pénalisé les performances d'ouverture des fenêtres.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QProxyStyle, QStyle


class MM3ProxyStyle(QProxyStyle):
    """Conserve le style natif mais rend les ascenseurs plus faciles à saisir."""

    SCROLLBAR_EXTENT = 20
    SCROLLBAR_SLIDER_MIN = 32

    def pixelMetric(self, metric, option=None, widget=None):  # noqa: N802 - API Qt
        value = super().pixelMetric(metric, option, widget)
        if metric == QStyle.PixelMetric.PM_ScrollBarExtent:
            return max(int(value), self.SCROLLBAR_EXTENT)
        if metric == QStyle.PixelMetric.PM_ScrollBarSliderMin:
            return max(int(value), self.SCROLLBAR_SLIDER_MIN)
        return value

    def styleHint(self, hint, option=None, widget=None, returnData=None):  # noqa: N802 - API Qt
        # Les ascenseurs transitoires peuvent devenir très discrets. MM3 préfère
        # une barre persistante, surtout dans les longues listes déroulantes.
        if hint == QStyle.StyleHint.SH_ScrollBar_Transient:
            return 0
        return super().styleHint(hint, option, widget, returnData)

    @staticmethod
    def _full_width_slider_rect(rect, option):
        """Élargit uniquement l'axe transversal du curseur.

        Certains styles Windows dessinent un curseur très fin au centre d'un
        couloir pourtant large. Pour MM3, le curseur doit occuper presque tout
        le couloir afin d'être facile à attraper à la souris.
        """
        out = rect
        orientation = getattr(option, "orientation", Qt.Orientation.Vertical)
        if orientation == Qt.Orientation.Vertical:
            out.setLeft(option.rect.left())
            out.setRight(option.rect.right())
        else:
            out.setTop(option.rect.top())
            out.setBottom(option.rect.bottom())
        return out

    def subControlRect(self, control, option, subControl, widget=None):  # noqa: N802 - API Qt
        rect = super().subControlRect(control, option, subControl, widget)
        if (
            control == QStyle.ComplexControl.CC_ScrollBar
            and subControl == QStyle.SubControl.SC_ScrollBarSlider
        ):
            return self._full_width_slider_rect(rect, option)
        return rect

    def hitTestComplexControl(self, control, option, pos, widget=None):  # noqa: N802 - API Qt
        if control == QStyle.ComplexControl.CC_ScrollBar:
            slider = self.subControlRect(
                control,
                option,
                QStyle.SubControl.SC_ScrollBarSlider,
                widget,
            )
            if slider.contains(pos):
                return QStyle.SubControl.SC_ScrollBarSlider
        return super().hitTestComplexControl(control, option, pos, widget)

    def drawComplexControl(self, control, option, painter, widget=None):  # noqa: N802 - API Qt
        """Dessine les ascenseurs MM3 en 2D, sans aucun rendu natif 3D.

        Point important : pour CC_ScrollBar on ne délègue volontairement PAS
        au style Windows. Ainsi aucun curseur 3D ne peut réapparaître sous ou
        au-dessus du curseur MM3. Pour tous les autres contrôles, le style
        natif est conservé.
        """
        if control != QStyle.ComplexControl.CC_ScrollBar:
            super().drawComplexControl(control, option, painter, widget)
            return

        rect = option.rect
        if not rect.isValid() or rect.isEmpty():
            return

        slider = self.subControlRect(
            control, option, QStyle.SubControl.SC_ScrollBarSlider, widget
        )

        painter.save()
        # Glissière claire, entièrement plate.
        painter.fillRect(rect, QColor(238, 238, 238))

        if slider.isValid() and not slider.isEmpty():
            # Le curseur occupe toute la largeur/hauteur transversale de la
            # glissière : pas de marge, pas de bordure, pas de relief.
            active = getattr(option, "activeSubControls", QStyle.SubControl.SC_None)
            state = getattr(option, "state", QStyle.StateFlag.State_None)
            if (active & QStyle.SubControl.SC_ScrollBarSlider) and (state & QStyle.StateFlag.State_Sunken):
                color = QColor(104, 104, 104)
            elif (active & QStyle.SubControl.SC_ScrollBarSlider) and (state & QStyle.StateFlag.State_MouseOver):
                color = QColor(122, 122, 122)
            else:
                color = QColor(145, 145, 145)
            painter.fillRect(slider, color)

        painter.restore()
