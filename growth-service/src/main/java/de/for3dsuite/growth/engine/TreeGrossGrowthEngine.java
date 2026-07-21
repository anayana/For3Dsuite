package de.for3dsuite.growth.engine;

import de.for3dsuite.growth.model.Dtos.Period;
import de.for3dsuite.growth.model.Dtos.ProjectedTree;
import de.for3dsuite.growth.model.Dtos.SimulateRequest;
import de.for3dsuite.growth.model.Dtos.SimulationResult;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;

import treegross.base.SpeciesDefMap;
import treegross.base.Stand;
import treegross.base.Tree;

import java.time.Year;
import java.util.ArrayList;
import java.util.List;

/**
 * Adapter auf die echte TreeGrOSS/BWINPro-Engine (NW-FVA, GPLv3).
 *
 * Diese Klasse ist die EINZIGE Stelle, an der GPL-Code beruehrt wird: rein
 * Mapping DTO -> treegross.base.Stand -> DTO. Die Bibliothek liegt nicht im
 * Repo, sondern wird per lib/fetch_treegross.sh geholt (siehe README).
 *
 * Aktivierung: application.properties
 *   growth.engine=treegross
 *   growth.treegross.model=lib/src/treegross/model/ForestSimulatorNWGermany6.xml
 *
 * Drei Fallstricke, am realen Lauf verifiziert (Renon, 87 Staemme, tools/):
 *
 *  1. out = -1 bedeutet LEBEND. Tree.java: "if living -1, else the year when
 *     died or taken out". Mit out = 0 gelten alle Baeume als ausgeschieden und
 *     wachsen ueberhaupt nicht.
 *  2. si = -9 uebergeben, damit TreeGrOSS die Bonitaet selbst herleitet
 *     (Tree.java: "if (si <= -9.0 ...) si = calculateSiteIndex()"). Bei si = 0
 *     findet kein Hoehenwachstum statt.
 *  3. Modelldatei mit voll qualifizierten Plugin-Namen waehlen: die aeltere
 *     ForestSimulatorNWGermany.xml nennt "Competition" statt
 *     "treegross.base.Competition" -> ClassNotFoundException beim Laden.
 *
 * grow(period, ...) zaehlt Stand.year selbst hoch; die Periodenjahre werden
 * daher direkt aus dem Stand gelesen.
 */
@Component
@ConditionalOnProperty(name = "growth.engine", havingValue = "treegross")
public class TreeGrossGrowthEngine implements GrowthEngine {

    /** Artdefinitionen einmalig laden (empfohlener Weg laut Stand.setSDM). */
    private final SpeciesDefMap sdm;
    private final boolean naturalIngrowth;

    public TreeGrossGrowthEngine(
            @Value("${growth.treegross.model}") String modelPath,
            @Value("${growth.treegross.natural-ingrowth:false}") boolean naturalIngrowth) {
        this.sdm = new SpeciesDefMap();
        this.sdm.readFromPath(modelPath);
        this.naturalIngrowth = naturalIngrowth;
    }

    @Override
    public SimulationResult simulate(SimulateRequest request) {
        var reqStand = request.stand();
        int years = request.simulate() != null && request.simulate().years() != null
                ? request.simulate().years() : 20;
        int step = request.simulate() != null && request.simulate().step_years() != null
                ? request.simulate().step_years() : 5;
        int standAge = reqStand != null && reqStand.age_years() != null
                ? reqStand.age_years() : 0;

        Stand st = new Stand();
        st.debug = false;
        st.setSDM(sdm);
        st.standname = reqStand != null && reqStand.id() != null ? reqStand.id() : "stand";
        st.size = reqStand != null && reqStand.area_ha() != null ? reqStand.area_ha() : 1.0;
        st.year = Year.now().getValue();

        int added = 0;
        for (var t : request.trees()) {
            if (t.dbh_cm() == null || t.height_m() == null || t.species() == null) {
                continue;
            }
            int age = t.age_years() != null ? (int) Math.round(t.age_years()) : standAge;
            double cb = t.crown_base_m() != null ? t.crown_base_m() : 0.0;
            double x = t.x() != null ? t.x() : 0.0;
            double y = t.y() != null ? t.y() : 0.0;
            try {
                if (st.addtree(t.species(), t.id(), age, -1,          // -1 = lebend
                        t.dbh_cm(), t.height_m(), cb, 0.0,
                        -9.0,                                         // Bonitaet herleiten
                        x, y, 0.0, 0, 0, 0)) {
                    added++;
                }
            } catch (Exception e) {   // u. a. SpeciesNotDefinedException
                throw new IllegalArgumentException(
                        "Baum " + t.id() + " (Artcode " + t.species() + ") abgelehnt: "
                        + e.getMessage(), e);
            }
        }
        if (added == 0) {
            throw new IllegalArgumentException("Keine gueltigen Baeume in der Anfrage");
        }

        st.descspecies();
        st.missingData();          // ergaenzt Eckpunkte, fehlende Hoehen/Kronen

        List<Period> periods = new ArrayList<>();
        periods.add(snapshot(st));
        for (int grown = 0; grown < years; grown += step) {
            st.grow(Math.min(step, years - grown), naturalIngrowth);
            periods.add(snapshot(st));
        }
        return new SimulationResult(reqStand, periods);
    }

    /** Aktuellen Standzustand als Periode abbilden (lebend = out < 0). */
    private Period snapshot(Stand st) {
        List<ProjectedTree> trees = new ArrayList<>();
        for (int i = 0; i < st.ntrees; i++) {
            Tree t = st.tr[i];
            if (t == null) {
                continue;
            }
            boolean alive = t.out < 0;
            trees.add(new ProjectedTree(t.no, round(t.d), round(t.h), alive, !alive));
        }
        return new Period(st.year, trees);
    }

    private static Double round(double v) {
        return Math.round(v * 10.0) / 10.0;
    }

    @Override
    public String name() {
        return "treegross";
    }
}
