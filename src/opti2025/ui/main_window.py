from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from opti2025.cleanup import CleanupResult, restore_latest_backup, safe_cleanup
from opti2025.max_performance import (
    MaxPerformanceResult,
    apply_max_performance_profile,
    restore_latest_max_performance,
)
from opti2025.performance import (
    PerformanceResult,
    apply_performance_profile,
    restore_latest_performance,
)


@dataclass(frozen=True)
class ProfileDefinition:
    name: str
    description: str
    accent: str


class ProfileCard(QFrame):
    def __init__(
        self,
        profile: ProfileDefinition,
        action_label: str,
        safety_note: str,
        on_action: Callable[[], None],
        style_override: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.profile = profile
        self._on_action = on_action
        self.setObjectName("ProfileCard")
        self.setMinimumWidth(280)
        base_style = """
            QFrame#ProfileCard {
                background-color: #151b27;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 16px;
            }
            """
        self.setStyleSheet(style_override or base_style)

        title = QLabel(profile.name)
        title.setObjectName("ProfileTitle")
        title.setStyleSheet(
            f"color: {profile.accent}; font-size: 18px; font-weight: 700;"
        )

        description = QLabel(profile.description)
        description.setWordWrap(True)
        description.setStyleSheet("color: #c9d4ff; font-size: 13px;")

        safety_label = QLabel(safety_note)
        safety_label.setWordWrap(True)
        safety_label.setStyleSheet("color: #9fb0e5; font-size: 12px;")

        select_button = QPushButton(action_label)
        select_button.setCursor(Qt.PointingHandCursor)
        select_button.setStyleSheet(
            """
            QPushButton {
                background: #2c3b70;
                color: #e6eeff;
                border: none;
                padding: 10px 18px;
                border-radius: 10px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #344686;
            }
            """
        )
        select_button.clicked.connect(self._handle_select)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        layout.addWidget(title)
        layout.addWidget(description)
        layout.addWidget(safety_label)
        layout.addStretch()
        layout.addWidget(select_button)

    def _handle_select(self) -> None:
        self._on_action()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Opti2025 - Optimisation PC")
        self.setMinimumSize(900, 520)

        central = QWidget()
        self.setCentralWidget(central)
        self.setStyleSheet(
            """
            QMainWindow {
                background-color: #0b0f1a;
            }
            QLabel#HeroTitle {
                color: #f3f6ff;
                font-size: 32px;
                font-weight: 700;
            }
            QLabel#HeroSubtitle {
                color: #9fb0e5;
                font-size: 14px;
            }
            """
        )

        layout = QVBoxLayout(central)
        layout.setContentsMargins(40, 32, 40, 32)
        layout.setSpacing(24)

        header = QVBoxLayout()
        title = QLabel("Opti2025")
        title.setObjectName("HeroTitle")
        subtitle = QLabel(
            "Sélectionnez un profil pour appliquer des optimisations réversibles."
        )
        subtitle.setObjectName("HeroSubtitle")
        subtitle.setWordWrap(True)

        header.addWidget(title)
        header.addWidget(subtitle)

        cards_row = QHBoxLayout()
        cards_row.setSpacing(20)
        cards_row.addStretch()

        safe_profile = ProfileDefinition(
            name="Safe",
            description=(
                "Nettoie les fichiers temporaires Windows et le dossier TEMP utilisateur "
                "sans modifier vos réglages."
            ),
            accent="#6ee7b7",
        )

        cards_row.addWidget(
            ProfileCard(
                safe_profile,
                action_label="Nettoyer maintenant",
                safety_note="Sans risque, sans droits admin et avec restauration possible.",
                on_action=self._run_safe_cleanup,
            )
        )

        performance_profile = ProfileDefinition(
            name="Performance",
            description=(
                "Désactive OneDrive au démarrage et réduit les apps en arrière-plan "
                "sans toucher aux services critiques."
            ),
            accent="#60a5fa",
        )
        cards_row.addWidget(
            ProfileCard(
                performance_profile,
                action_label="Appliquer",
                safety_note="Avertissement modéré, réversible via Restore.",
                on_action=self._run_performance_profile,
            )
        )
        max_profile = ProfileDefinition(
            name="Max Performance (Expert)",
            description=(
                "Désactive des services non critiques, l'indexation Windows et applique "
                "un plan d'alimentation haute performance."
            ),
            accent="#f97316",
        )
        max_style = """
            QFrame#ProfileCard {
                background-color: #1b1214;
                border: 1px solid rgba(249, 115, 22, 0.6);
                border-radius: 16px;
            }
            """
        cards_row.addWidget(
            ProfileCard(
                max_profile,
                action_label="Appliquer (Expert)",
                safety_note="Avertissement : droits administrateur requis.",
                on_action=self._run_max_performance_profile,
                style_override=max_style,
            )
        )
        cards_row.addStretch()

        summary_frame = QFrame()
        summary_frame.setObjectName("SummaryFrame")
        summary_frame.setStyleSheet(
            """
            QFrame#SummaryFrame {
                background-color: #101624;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 14px;
            }
            """
        )
        summary_layout = QVBoxLayout(summary_frame)
        summary_layout.setContentsMargins(18, 16, 18, 16)
        summary_layout.setSpacing(16)

        safe_section = self._build_summary_section(
            title="Résumé Safe",
            default_text="Aucune action Safe exécutée pour le moment.",
            restore_label="Restaurer Safe",
            restore_handler=self._restore_safe_cleanup,
        )
        self.safe_summary_label = safe_section["label"]

        performance_section = self._build_summary_section(
            title="Résumé Performance",
            default_text="Aucune action Performance exécutée pour le moment.",
            restore_label="Restaurer Performance",
            restore_handler=self._restore_performance_profile,
        )
        self.performance_summary_label = performance_section["label"]

        max_section = self._build_summary_section(
            title="Résumé Max Performance",
            default_text="Aucune action Max Performance exécutée pour le moment.",
            restore_label="Restaurer Max",
            restore_handler=self._restore_max_performance_profile,
        )
        self.max_summary_label = max_section["label"]

        summary_layout.addWidget(safe_section["frame"])
        summary_layout.addWidget(performance_section["frame"])
        summary_layout.addWidget(max_section["frame"])

        layout.addLayout(header)
        layout.addSpacing(8)
        layout.addLayout(cards_row)
        layout.addWidget(summary_frame)
        layout.addStretch()

        footer = QLabel("PySide6 · Préparation PyInstaller · Version UI")
        footer.setStyleSheet("color: #4d5a83; font-size: 12px;")
        layout.addWidget(footer)

    def _run_safe_cleanup(self) -> None:
        result = safe_cleanup()
        self.safe_summary_label.setText(
            self._format_safe_result(result, "Nettoyage Safe terminé")
        )

    def _restore_safe_cleanup(self) -> None:
        result = restore_latest_backup()
        self.safe_summary_label.setText(
            self._format_safe_result(result, "Restauration Safe terminée")
        )

    def _run_performance_profile(self) -> None:
        confirm = QMessageBox.warning(
            self,
            "Avertissement Performance",
            (
                "Le profil Performance désactive OneDrive au démarrage et réduit les "
                "apps en arrière-plan utilisateur. Ces actions sont réversibles via "
                "le bouton Restore."
            ),
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        result = apply_performance_profile()
        self.performance_summary_label.setText(
            self._format_performance_result(
                result, "Profil Performance appliqué"
            )
        )

    def _restore_performance_profile(self) -> None:
        result = restore_latest_performance()
        self.performance_summary_label.setText(
            self._format_performance_result(
                result, "Restauration Performance terminée"
            )
        )

    def _run_max_performance_profile(self) -> None:
        first_confirm = QMessageBox.warning(
            self,
            "Avertissement Max Performance",
            (
                "Le profil Max Performance nécessite des droits administrateur et "
                "désactive des services Windows NON critiques, l'indexation Search et "
                "modifie le plan d'alimentation. Assurez-vous de comprendre les impacts."
            ),
            QMessageBox.Yes | QMessageBox.No,
        )
        if first_confirm != QMessageBox.Yes:
            return
        second_confirm = QMessageBox.warning(
            self,
            "Confirmation finale",
            "Confirmez-vous l'application du profil Max Performance ?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if second_confirm != QMessageBox.Yes:
            return
        result = apply_max_performance_profile()
        self.max_summary_label.setText(
            self._format_max_performance_result(
                result, "Profil Max Performance appliqué"
            )
        )

    def _restore_max_performance_profile(self) -> None:
        result = restore_latest_max_performance()
        self.max_summary_label.setText(
            self._format_max_performance_result(
                result, "Restauration Max Performance terminée"
            )
        )

    @staticmethod
    def _format_safe_result(result: CleanupResult, title: str) -> str:
        backup_info = (
            f"Sauvegarde : {result.backup_dir}"
            if result.backup_dir
            else "Aucune sauvegarde créée."
        )
        if result.errors:
            error_lines = "\n".join(f"- {error}" for error in result.errors[:3])
            errors_info = f"Erreurs : {len(result.errors)}\n{error_lines}"
        else:
            errors_info = "Aucune erreur."
        return (
            f"{title}\n"
            f"Éléments analysés : {result.scanned}\n"
            f"Éléments déplacés : {result.moved}\n"
            f"Échecs : {result.failed} · Ignorés : {result.skipped}\n"
            f"{backup_info}\n"
            f"{errors_info}"
        )

    @staticmethod
    def _format_performance_result(
        result: PerformanceResult, title: str
    ) -> str:
        onedrive_status = (
            "Désactivé"
            if result.onedrive_disabled
            else "Inchangé"
        )
        background_status = (
            "Réduit"
            if result.background_apps_disabled
            else "Inchangé"
        )
        process_status = (
            "Arrêté"
            if result.onedrive_process_stopped
            else "Non modifié"
        )
        backup_info = (
            f"Sauvegarde : {result.backup_dir}"
            if result.backup_dir
            else "Aucune sauvegarde créée."
        )
        if result.errors:
            error_lines = "\n".join(f"- {error}" for error in result.errors[:3])
            errors_info = f"Erreurs : {len(result.errors)}\n{error_lines}"
        else:
            errors_info = "Aucune erreur."
        return (
            f"{title}\n"
            f"OneDrive démarrage : {onedrive_status}\n"
            f"Apps en arrière-plan : {background_status}\n"
            f"Processus OneDrive : {process_status}\n"
            f"{backup_info}\n"
            f"{errors_info}"
        )

    @staticmethod
    def _format_max_performance_result(
        result: MaxPerformanceResult, title: str
    ) -> str:
        services_info = (
            ", ".join(result.services_disabled)
            if result.services_disabled
            else "Aucun service désactivé."
        )
        indexing_info = "Désactivée" if result.indexing_disabled else "Inchangée"
        power_info = (
            "Activé" if result.power_scheme_set else "Non modifié"
        )
        onedrive_info = (
            "Désactivé"
            if result.onedrive_disabled
            else "Inchangé"
        )
        process_info = (
            "Arrêté" if result.onedrive_process_stopped else "Non modifié"
        )
        backup_info = (
            f"Sauvegarde : {result.backup_dir}"
            if result.backup_dir
            else "Aucune sauvegarde créée."
        )
        if result.errors:
            error_lines = "\n".join(f"- {error}" for error in result.errors[:3])
            errors_info = f"Erreurs : {len(result.errors)}\n{error_lines}"
        else:
            errors_info = "Aucune erreur."
        return (
            f"{title}\n"
            f"Services désactivés : {services_info}\n"
            f"Indexation Windows : {indexing_info}\n"
            f"Plan d'alimentation : {power_info}\n"
            f"OneDrive démarrage : {onedrive_info}\n"
            f"Processus OneDrive : {process_info}\n"
            f"{backup_info}\n"
            f"{errors_info}"
        )

    @staticmethod
    def _build_summary_section(
        title: str,
        default_text: str,
        restore_label: str,
        restore_handler: Callable[[], None],
    ) -> dict[str, QWidget]:
        section_frame = QFrame()
        section_frame.setStyleSheet(
            """
            QFrame {
                background-color: #0f1523;
                border: 1px solid rgba(255, 255, 255, 0.06);
                border-radius: 12px;
            }
            """
        )
        section_layout = QVBoxLayout(section_frame)
        section_layout.setContentsMargins(14, 12, 14, 12)
        section_layout.setSpacing(8)

        section_title = QLabel(title)
        section_title.setStyleSheet(
            "color: #f3f6ff; font-size: 14px; font-weight: 600;"
        )
        summary_label = QLabel(default_text)
        summary_label.setWordWrap(True)
        summary_label.setStyleSheet("color: #c9d4ff; font-size: 13px;")

        restore_button = QPushButton(restore_label)
        restore_button.setCursor(Qt.PointingHandCursor)
        restore_button.setStyleSheet(
            """
            QPushButton {
                background: #23304d;
                color: #e6eeff;
                border: none;
                padding: 8px 14px;
                border-radius: 8px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #2b3a5f;
            }
            """
        )
        restore_button.clicked.connect(restore_handler)

        section_layout.addWidget(section_title)
        section_layout.addWidget(summary_label)
        section_layout.addWidget(restore_button, alignment=Qt.AlignLeft)

        return {"frame": section_frame, "label": summary_label}
