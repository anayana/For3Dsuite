import treegross.base.Stand;
import treegross.base.Tree;

import java.io.BufferedReader;
import java.io.FileReader;

/**
 * Standalone-Pruefstand fuer die echte TreeGrOSS-Engine (ohne Spring/Maven).
 * Belegt, dass Artcodes, Baumliste und Wachstumsschritt mit der GPL-JAR laufen.
 *
 *   javac -cp treegross.jar -d out TreeGrossHarness.java
 *   java  -cp treegross.jar:out TreeGrossHarness <model.xml> <trees.tsv> <jahre> <schritt> <alter> <flaeche_ha>
 *
 * trees.tsv: id<TAB>artcode<TAB>bhd_cm<TAB>hoehe_m  (eine Zeile je Baum, ohne Header)
 */
public class TreeGrossHarness {

    public static void main(String[] args) throws Exception {
        String model = args[0];
        String tsv = args[1];
        int years = Integer.parseInt(args[2]);
        int step = Integer.parseInt(args[3]);
        int age = Integer.parseInt(args[4]);
        double areaHa = Double.parseDouble(args[5]);

        Stand st = new Stand();
        st.debug = false;
        st.loadSDM(model);
        st.standname = "harness";
        st.size = areaHa;
        st.year = 2024;
        st.monat = 8;

        int added = 0, failed = 0;
        try (BufferedReader br = new BufferedReader(new FileReader(tsv))) {
            String line;
            while ((line = br.readLine()) != null) {
                if (line.isBlank()) continue;
                String[] f = line.split("\t");
                String id = f[0];
                int code = Integer.parseInt(f[1].trim());
                double d = Double.parseDouble(f[2].trim());
                double h = Double.parseDouble(f[3].trim());
                try {
                    // out = -1 bedeutet lebend (Tree.java: "if living -1, else the
                    // year when died or taken out").
                    // si = -9 laesst TreeGrOSS die Bonitaet selbst herleiten
                    // (Tree.java: "if (si <= -9.0 ...) si = calculateSiteIndex()");
                    // bei si = 0 findet KEIN Hoehenwachstum statt.
                    boolean ok = st.addtree(code, id, age, -1, d, h, 0, 0, -9.0,
                                            0, 0, 0, 0, 0, 0);
                    if (ok) added++; else failed++;
                } catch (Exception e) {
                    failed++;
                    if (failed <= 3) {
                        System.out.println("  addtree fehlgeschlagen (" + code + "): "
                                           + e.getClass().getSimpleName() + " " + e.getMessage());
                    }
                }
            }
        }
        System.out.println("Baeume eingelesen: " + added + " (fehlgeschlagen: " + failed + ")");

        st.descspecies();
        st.missingData();
        System.out.printf("Start  %d: ntrees=%d lebend=%d N/ha=%.0f G/ha=%.1f%n",
                st.year, st.ntrees, st.nTreesAlive, st.nha, st.bha);
        summarize(st, "  ");

        for (int s = step; s <= years; s += step) {
            st.grow(step, false);          // ohne natuerliche Verjuengung
            System.out.printf("+%2d J (%d): lebend=%d N/ha=%.0f G/ha=%.1f%n",
                    s, st.year, st.nTreesAlive, st.nha, st.bha);
            summarize(st, "  ");
        }
    }

    /** Mittleres BHD/Hoehe der lebenden Baeume. */
    private static void summarize(Stand st, String pad) {
        double sd = 0, sh = 0;
        int n = 0;
        for (int i = 0; i < st.ntrees; i++) {
            Tree t = st.tr[i];
            if (t == null || t.out >= 0) continue;   // lebend = out < 0
            sd += t.d; sh += t.h; n++;
        }
        if (n > 0) {
            System.out.printf("%smittl. BHD %.1f cm, mittl. Hoehe %.1f m (n=%d)%n",
                    pad, sd / n, sh / n, n);
        }
    }
}
