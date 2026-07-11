package de.for3dsuite.growth.model;

import java.util.List;

/**
 * JSON-Kontrakt des Wachstumsdienstes (stabil, versionierbar). Der TreeGrOSS-
 * Adapter mappt diese neutralen Felder auf die konkreten TreeGrOSS-Objekte;
 * Frontend/Pipeline kennen nur diese DTOs, nicht die GPL-Klassen.
 *
 * Erzeugt/gelesen auf der Python-Seite von scripts/treegross_export.py.
 */
public final class Dtos {
    private Dtos() {}

    /** Bestandesmetadaten. age_years und site_index (Bonitaet) sind die externe
     *  Hauptluecke (nicht aus der Punktwolke ableitbar). */
    public record Stand(
            String id,
            Double area_ha,
            Integer age_years,
            Double site_index,
            Double latitude,
            Double longitude) {}

    /** Ein Einzelbaum der Eingangs-Inventur. species = BWINPro/TreeGrOSS-Artcode. */
    public record Tree(
            String id,
            Integer species,
            Double dbh_cm,
            Double height_m,
            Double x,
            Double y,
            Double crown_base_m,
            Double age_years,
            Boolean out_of_stand) {}

    /** Simulationssteuerung. */
    public record SimulateSpec(Integer years, Integer step_years) {}

    /** Vollstaendige Anfrage an POST /simulate. */
    public record SimulateRequest(Stand stand, SimulateSpec simulate, List<Tree> trees) {}

    /** Zustand eines Baumes zu einem Prognosezeitpunkt. */
    public record ProjectedTree(
            String id,
            Double dbh_cm,
            Double height_m,
            Boolean alive,
            Boolean removed) {}

    /** Ein Prognosezeitpunkt (Jahr) mit dem Bestand zu diesem Zeitpunkt. */
    public record Period(Integer year, List<ProjectedTree> trees) {}

    /** Antwort von POST /simulate. */
    public record SimulationResult(Stand stand, List<Period> periods) {}
}
