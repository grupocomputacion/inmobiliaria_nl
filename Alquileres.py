import sqlite3
import pandas as pd
import os
import sys
import subprocess
import tkinter as tk
from tkinter import messagebox, ttk, simpledialog
from datetime import datetime, timedelta

# Función de rutas para que el EXE encuentre su propia carpeta
def obtener_ruta(nombre_archivo):
    if getattr(sys, 'frozen', False):
        directorio = os.path.dirname(sys.executable)
    else:
        directorio = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(directorio, nombre_archivo)

class SistemaInmobiliaria:
    def __init__(self, root):
        self.root = root
        self.root.title("Gestión Inmobiliaria Pro - v38")
        self.root.geometry("1450x900")
        
        # Base de datos en la misma carpeta que el EXE
        self.db_name = obtener_ruta("datos_alquileres.db")
        self.conn = sqlite3.connect(self.db_name)
        self.cursor = self.conn.cursor()
        self.inicializar_db()
        
        # Estilo Excel
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", rowheight=35, font=('Arial', 12), borderwidth=1)
        style.configure("Treeview.Heading", font=('Arial', 12, 'bold'))
        style.map("Treeview", background=[('selected', '#347083')])

        self.tabs = ttk.Notebook(self.root)
        self.tabs.pack(expand=1, fill="both")
        
        # Pestañas
        self.tab_inv = ttk.Frame(self.tabs)
        self.tab_con = ttk.Frame(self.tabs)
        self.tab_cob = ttk.Frame(self.tabs)
        self.tab_caj = ttk.Frame(self.tabs)
        
        self.tabs.add(self.tab_inv, text="🏠 Inventario")
        self.tabs.add(self.tab_con, text="✍️ Contratos")
        self.tabs.add(self.tab_cob, text="📋 Cobranzas")
        self.tabs.add(self.tab_caj, text="📊 Caja")

        self.setup_tab_inventario()
        self.setup_tab_contratos()
        self.setup_tab_cobros()
        self.setup_tab_caja()
        self.act_todo()
        
        tk.Button(self.root, text="❌ CERRAR SISTEMA", command=self.salir_seguro).pack(side="bottom", pady=5)

    def inicializar_db(self):
        self.cursor.executescript('''
            CREATE TABLE IF NOT EXISTS bloques (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE);
            CREATE TABLE IF NOT EXISTS inmuebles (id INTEGER PRIMARY KEY AUTOINCREMENT, id_bloque INTEGER, tipo TEXT, precio_alquiler REAL, costo_contrato REAL, deposito_base REAL, estado TEXT DEFAULT 'Libre');
            CREATE TABLE IF NOT EXISTS inquilinos (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT, celular TEXT, procedencia TEXT, grupo TEXT, em_nombre TEXT, em_tel TEXT);
            CREATE TABLE IF NOT EXISTS contratos (id INTEGER PRIMARY KEY AUTOINCREMENT, id_inmueble INTEGER, id_inquilino INTEGER, fecha_inicio DATE, meses INTEGER, activo INTEGER DEFAULT 1, monto_alquiler REAL, monto_contrato REAL, monto_deposito REAL);
            CREATE TABLE IF NOT EXISTS deudas (id INTEGER PRIMARY KEY AUTOINCREMENT, id_contrato INTEGER, concepto TEXT, mes_anio TEXT, monto_debe REAL, monto_pago REAL DEFAULT 0, pagado INTEGER DEFAULT 0, fecha_cobro DATE);
        ''')
        self.conn.commit()

    def fmt_moneda(self, valor):
        try: return f"$ {int(float(valor or 0)):,}".replace(",", ".")
        except: return "$ 0"

    def abrir_txt(self, n, c):
        p = obtener_ruta(f"{n}.txt")
        # Forzamos codificación ANSI para que Windows NotePad lo lea bien
        with open(p, "w", encoding='latin-1') as f: f.write(c)
        os.startfile(p) # Comando nativo de Windows para abrir archivos

    def salir_seguro(self):
        self.conn.close()
        self.root.destroy()

    # --- INVENTARIO (Filtros y ID 50px) ---
    def setup_tab_inventario(self):
        f_main = tk.Frame(self.tab_inv); f_main.pack(fill="both", expand=True)
        f_form = tk.LabelFrame(f_main, text="Ficha Técnica", padx=10, pady=10); f_form.pack(side="left", fill="y", padx=10, pady=10)
        
        tk.Label(f_form, text="Nuevo Bloque:").pack(anchor="w")
        self.ent_nuevo_bloque = tk.Entry(f_form); self.ent_nuevo_bloque.pack(fill="x", pady=2)
        tk.Button(f_form, text="➕ Crear Bloque", command=self.crear_bloque).pack(fill="x", pady=5)
        
        tk.Label(f_form, text="Bloque:").pack(anchor="w")
        self.cb_bloque_inv = ttk.Combobox(f_form, state="readonly"); self.cb_bloque_inv.pack(fill="x", pady=2)
        
        self.inm_id_var = tk.StringVar(value="Nuevo")
        self.labels_inm = ["Nombre Unidad", "Alquiler $", "Contrato $", "Depósito $"]
        self.inm_ents = {l: tk.Entry(f_form) for l in self.labels_inm}
        for l in self.labels_inm:
            tk.Label(f_form, text=l).pack(anchor="w"); self.inm_ents[l].pack(fill="x", pady=2)
            
        tk.Button(f_form, text="💾 GUARDAR", bg="#AED581", command=self.save_inm).pack(fill="x", pady=10)
        
        f_der = tk.Frame(f_main); f_der.pack(side="right", fill="both", expand=True, padx=10, pady=10)
        f_fil = tk.Frame(f_der); f_fil.pack(fill="x", pady=(0, 10))
        tk.Label(f_fil, text="BLOQUE:").pack(side="left", padx=5)
        self.combo_ver_bloque = ttk.Combobox(f_fil, state="readonly", width=15); self.combo_ver_bloque.pack(side="left", padx=5); self.combo_ver_bloque.bind("<<ComboboxSelected>>", lambda e: self.act_tree_inv())
        tk.Label(f_fil, text="ESTADO:").pack(side="left", padx=5)
        self.combo_ver_estado = ttk.Combobox(f_fil, values=["Todos", "Libre", "Ocupado"], state="readonly", width=10); self.combo_ver_estado.current(0); self.combo_ver_estado.pack(side="left", padx=5); self.combo_ver_estado.bind("<<ComboboxSelected>>", lambda e: self.act_tree_inv())

        self.tree_inv = ttk.Treeview(f_der, columns=("ID", "Bloque", "Unidad", "Alquiler", "Contrato", "Depósito", "Estado"), show='headings')
        self.tree_inv.heading("ID", text="ID"); self.tree_inv.column("ID", width=50, anchor="center")
        for c in ("Bloque", "Unidad", "Alquiler", "Contrato", "Depósito", "Estado"): self.tree_inv.heading(c, text=c); self.tree_inv.column(c, anchor="center", width=120)
        self.tree_inv.pack(fill="both", expand=True); self.tree_inv.bind("<<TreeviewSelect>>", self.cargar_inm_para_editar)

    # --- CONTRATOS ---
    def setup_tab_contratos(self):
        f = tk.Frame(self.tab_con, padx=20, pady=10); f.pack(fill="both")
        f_alta = tk.LabelFrame(f, text="Nuevo Contrato", padx=10, pady=10); f_alta.pack(fill="x")
        tk.Label(f_alta, text="Seleccionar Unidad LIBRE:", font=("bold")).grid(row=0, column=0, sticky="w")
        self.cb_inm_con = ttk.Combobox(f_alta, state="readonly", width=40); self.cb_inm_con.grid(row=0, column=1, pady=10); self.cb_inm_con.bind("<<ComboboxSelected>>", self.cargar_precios_contrato)
        tk.Label(f_alta, text="Meses:").grid(row=0, column=2); self.ent_meses = tk.Entry(f_alta, width=5); self.ent_meses.insert(0, "6"); self.ent_meses.grid(row=0, column=3)
        self.lbl_v_alq, self.lbl_v_con, self.lbl_v_dep = tk.Label(f_alta, text="$ 0", fg="blue"), tk.Label(f_alta, text="$ 0", fg="blue"), tk.Label(f_alta, text="$ 0", fg="blue")
        tk.Label(f_alta, text="Alquiler:").grid(row=1, column=0); self.lbl_v_alq.grid(row=1, column=1)
        tk.Label(f_alta, text="Contrato:").grid(row=1, column=2); self.lbl_v_con.grid(row=1, column=3)
        tk.Label(f_alta, text="Depósito:").grid(row=1, column=4); self.lbl_v_dep.grid(row=1, column=5)
        self.inq_ents = {l: tk.Entry(f_alta) for l in ["Nombre:", "Celular:", "Procedencia:", "Grupo:", "Emerg. Nom:", "Emerg. Tel:"]}
        for i, (l, e) in enumerate(self.inq_ents.items()): tk.Label(f_alta, text=l).grid(row=i//3+2, column=(i%3)*2, pady=5); e.grid(row=i//3+2, column=(i%3)*2+1, padx=5)
        tk.Button(f_alta, text="🤝 GENERAR CONTRATO", bg="#C8E6C9", command=self.vincular_contrato).grid(row=5, column=0, columnspan=6, pady=15, sticky="ew")
        f_baja = tk.LabelFrame(f, text="Baja", padx=10, pady=10); f_baja.pack(fill="x", pady=20)
        self.cb_baja = ttk.Combobox(f_baja, state="readonly", width=50); self.cb_baja.pack(side="left", padx=10)
        tk.Button(f_baja, text="🔓 DAR DE BAJA", bg="#FFCDD2", command=self.ejecutar_baja).pack(side="right")

    # --- COBRANZAS ---
    def setup_tab_cobros(self):
        f = tk.Frame(self.tab_cob, padx=10, pady=10); f.pack(fill="both", expand=True)
        tk.Label(f, text="BUSCAR INQUILINO:", font=("bold")).pack(anchor="w")
        self.ent_bus_cob = tk.Entry(f, font=("Arial", 12)); self.ent_bus_cob.pack(fill="x", pady=5); self.ent_bus_cob.bind("<KeyRelease>", lambda e: self.act_combos())
        self.cb_cob = ttk.Combobox(f, state="readonly", width=80); self.cb_cob.pack(pady=10); self.cb_cob.bind("<<ComboboxSelected>>", self.act_tree_cob)
        self.tree_cob = ttk.Treeview(f, columns=("ID", "Concepto", "Mes", "Debe", "Abonado", "Saldo"), show='headings')
        self.tree_cob.heading("ID", text="ID"); self.tree_cob.column("ID", width=50, anchor="center")
        for c in ("Concepto", "Mes", "Debe", "Abonado", "Saldo"): self.tree_cob.heading(c, text=c); self.tree_cob.column(c, anchor="center", width=140)
        self.tree_cob.pack(fill="both", expand=True)
        tk.Button(f, text="💰 COBRAR Y RECIBO", bg="#FFF59D", command=self.cobrar_items_parcial).pack(fill="x", pady=10)

    # --- CAJA ---
    def setup_tab_caja(self):
        f = tk.Frame(self.tab_caj, padx=10, pady=10); f.pack(fill="both", expand=True)
        tk.Button(f, text="📊 EXCEL", command=self.exportar_excel).pack(pady=10)
        self.tree_caja = ttk.Treeview(f, columns=("Fecha", "Unidad", "Concepto", "Monto"), show='headings')
        for c in ("Fecha", "Unidad", "Concepto", "Monto"): self.tree_caja.heading(c, text=c); self.tree_caja.column(c, anchor="center", width=180)
        self.tree_caja.pack(fill="both", expand=True); self.lbl_tot = tk.Label(f, text="Total: $0", font=("bold", 18)); self.lbl_tot.pack()

    def exportar_excel(self):
        p = obtener_ruta("Caja.xlsx"); pd.read_sql_query("SELECT * FROM deudas WHERE monto_pago > 0", self.conn).to_excel(p, index=False); messagebox.showinfo("Ok", "Excel guardado")

    # --- LÓGICA ---
    def act_todo(self): self.act_tree_inv(); self.act_combos(); self.act_caja()

    def act_tree_inv(self):
        for i in self.tree_inv.get_children(): self.tree_inv.delete(i)
        b, e = self.combo_ver_bloque.get(), self.combo_ver_estado.get()
        q, p = "SELECT i.id, b.nombre, i.tipo, i.precio_alquiler, i.costo_contrato, i.deposito_base, i.estado FROM inmuebles i JOIN bloques b ON i.id_bloque = b.id WHERE 1=1", []
        if b and b != "TODOS": q += " AND b.nombre = ?"; p.append(b)
        if e and e != "Todos": q += " AND i.estado = ?"; p.append(e)
        for r in self.cursor.execute(q, p): self.tree_inv.insert("", "end", values=(r[0], r[1], r[2], self.fmt_moneda(r[3]), self.fmt_moneda(r[4]), self.fmt_moneda(r[5]), r[6]))

    def cobrar_items_parcial(self):
        sels = self.tree_cob.selection()
        if not sels: return
        sc = self.cb_cob.get(); idc = sc.split("#")[1].split("|")[0].strip(); ninq = sc.split("|")[1].strip(); tot, det = 0, ""
        for s in sels:
            v = self.tree_cob.item(s)['values']; deb, abo = float(str(v[3]).replace("$ ", "").replace(".", "")), float(str(v[4]).replace("$ ", "").replace(".", ""))
            p = simpledialog.askfloat("Pago", f"Saldo: {self.fmt_moneda(deb-abo)}", initialvalue=deb-abo)
            if p: self.cursor.execute("UPDATE deudas SET monto_pago=?, pagado=?, fecha_cobro=? WHERE id=?", (abo+p, 1 if (abo+p)>=deb else 0, datetime.now().strftime('%Y-%m-%d'), v[0])); tot += p; det += f"- {v[1]}: {self.fmt_moneda(p)}\n"
        if tot: self.conn.commit(); self.abrir_txt(f"Recibo_C{idc}", f"RECIBO Nº{idc}\nINQUILINO: {ninq}\n{det}\nTOTAL: {self.fmt_moneda(tot)}\n\nFIRMA: .........."); self.act_todo(); [self.tree_cob.delete(i) for i in self.tree_cob.get_children()]

    def vincular_contrato(self):
        try:
            idi = self.cb_inm_con.get().split("|")[0].split(":")[1].strip(); vinq = [e.get() for e in self.inq_ents.values()]
            if not vinq[0]: return
            self.cursor.execute("INSERT INTO inquilinos (nombre, celular, procedencia, grupo, em_nombre, em_tel) VALUES (?,?,?,?,?,?)", vinq); idq = self.cursor.lastrowid; mes = int(self.ent_meses.get()); al, co, de = self.tmp_val
            self.cursor.execute("INSERT INTO contratos (id_inmueble, id_inquilino, fecha_inicio, meses, monto_alquiler, monto_contrato, monto_deposito) VALUES (?,?,?,?,?,?,?)", (idi, idq, datetime.now().strftime('%Y-%m-%d'), mes, al, co, de)); idc = self.cursor.lastrowid
            self.cursor.execute("INSERT INTO deudas (id_contrato, concepto, mes_anio, monto_debe) VALUES (?, 'Contrato', 'Unico', ?)", (idc, co)); self.cursor.execute("INSERT INTO deudas (id_contrato, concepto, mes_anio, monto_debe) VALUES (?, 'Deposito', 'Unico', ?)", (idc, de))
            for m in range(mes): self.cursor.execute("INSERT INTO deudas (id_contrato, concepto, mes_anio, monto_debe) VALUES (?, 'Alquiler', ?, ?)", (idc, (datetime.now()+timedelta(days=30*m)).strftime('%m-%Y'), al))
            self.cursor.execute("UPDATE inmuebles SET estado='Ocupado' WHERE id=?", (idi,)); self.conn.commit()
            cue = f"CONTRATO Nº {idc}\nINQUILINO: {vinq[0]}\nPieza: {idi}\nALQUILER: {self.fmt_moneda(al)}\nDEPOSITO: {self.fmt_moneda(de)}\nCONTRATO: {self.fmt_moneda(co)}\n\nFIRMA: .........."
            self.abrir_txt(f"Contrato_{idc}", cue + "\n\n(DUPLICADO)\n" + cue); self.limpiar_contrato(); self.act_todo()
        except Exception as e: messagebox.showerror("Error", str(e))

    def act_combos(self):
        self.cb_inm_con['values'] = [f"ID: {r[0]} | {r[1]} - {r[2]}" for r in self.cursor.execute("SELECT i.id, b.nombre, i.tipo FROM inmuebles i JOIN bloques b ON i.id_bloque=b.id WHERE i.estado='Libre'")]
        bus = f"%{self.ent_bus_cob.get()}%"
        self.cb_cob['values'] = [f"Contrato #{r[0]} | {r[1]}" for r in self.cursor.execute("SELECT DISTINCT c.id, i.nombre FROM contratos c JOIN inquilinos i ON c.id_inquilino=i.id JOIN deudas d ON c.id = d.id_contrato WHERE c.activo=1 AND (d.monto_pago < d.monto_debe) AND (i.nombre LIKE ? OR c.id LIKE ?)", (bus, bus)).fetchall()]
        bloques = self.cursor.execute("SELECT id, nombre FROM bloques").fetchall()
        self.cb_bloque_inv['values'], self.combo_ver_bloque['values'] = [f"{r[0]}-{r[1]}" for r in bloques], ["TODOS"] + [r[1] for r in bloques]
        self.cb_baja['values'] = [f"Contrato #{r[0]} | {r[1]}" for r in self.cursor.execute("SELECT c.id, i.nombre FROM contratos c JOIN inquilinos i ON c.id_inquilino=i.id WHERE c.activo=1").fetchall()]

    def act_tree_cob(self, e):
        for i in self.tree_cob.get_children(): self.tree_cob.delete(i)
        if not self.cb_cob.get(): return
        idc = self.cb_cob.get().split("#")[1].split("|")[0].strip()
        for r in self.cursor.execute("SELECT id, concepto, mes_anio, monto_debe, monto_pago FROM deudas WHERE id_contrato=?", (idc,)): self.tree_cob.insert("", "end", values=(r[0], r[1], r[2], self.fmt_moneda(r[3]), self.fmt_moneda(r[4]), self.fmt_moneda(r[3]-r[4])))

    def act_caja(self):
        for i in self.tree_caja.get_children(): self.tree_caja.delete(i)
        t = 0
        for r in self.cursor.execute("SELECT d.fecha_cobro, i.tipo, d.concepto, d.monto_pago FROM deudas d JOIN contratos c ON d.id_contrato=c.id JOIN inmuebles i ON c.id_inmueble=i.id WHERE d.monto_pago > 0"): self.tree_caja.insert("", "end", values=(r[0], r[1], r[2], self.fmt_moneda(r[3]))); t += r[3]
        self.lbl_tot.config(text=f"Total: {self.fmt_moneda(t)}")

    def crear_bloque(self):
        n = self.ent_nuevo_bloque.get().strip()
        if n: self.cursor.execute("INSERT INTO bloques (nombre) VALUES (?)", (n,)); self.conn.commit(); self.act_combos(); self.ent_nuevo_bloque.delete(0, tk.END)

    def save_inm(self):
        b = self.cb_bloque_inv.get()
        if not b: return
        v = [b.split("-")[0]] + [self.inm_ents[l].get() for l in self.labels_inm]
        if self.inm_id_var.get() == "Nuevo": self.cursor.execute("INSERT INTO inmuebles (id_bloque, tipo, precio_alquiler, costo_contrato, deposito_base) VALUES (?,?,?,?,?)", v)
        else: v.append(self.inm_id_var.get()); self.cursor.execute("UPDATE inmuebles SET id_bloque=?, tipo=?, precio_alquiler=?, costo_contrato=?, deposito_base=? WHERE id=?", v)
        self.conn.commit(); self.limpiar_inm(); self.act_todo()

    def eliminar_inm(self):
        if self.inm_id_var.get() != "Nuevo": self.cursor.execute("DELETE FROM inmuebles WHERE id=?", (self.inm_id_var.get(),)); self.conn.commit(); self.limpiar_inm(); self.act_todo()

    def cargar_inm_para_editar(self, e):
        sel = self.tree_inv.selection(); 
        if not sel: return
        idi = self.tree_inv.item(sel)['values'][0]; r = self.cursor.execute("SELECT i.id, b.id || '-' || b.nombre, i.tipo, i.precio_alquiler, i.costo_contrato, i.deposito_base FROM inmuebles i JOIN bloques b ON i.id_bloque=b.id WHERE i.id=?", (idi,)).fetchone()
        self.inm_id_var.set(r[0]); self.cb_bloque_inv.set(r[1])
        for i, l in enumerate(self.labels_inm, 2): self.inm_ents[l].delete(0, tk.END); self.inm_ents[l].insert(0, r[i])

    def cargar_precios_contrato(self, e):
        idi = self.cb_inm_con.get().split("|")[0].split(":")[1].strip(); r = self.cursor.execute("SELECT precio_alquiler, costo_contrato, deposito_base FROM inmuebles WHERE id=?", (idi,)).fetchone()
        self.lbl_v_alq.config(text=self.fmt_moneda(r[0])); self.lbl_v_con.config(text=self.fmt_moneda(r[1])); self.lbl_v_dep.config(text=self.fmt_moneda(r[2])); self.tmp_val = r

    def ejecutar_baja(self):
        sel = self.cb_baja.get()
        if not sel: return
        idc = sel.split("#")[1].split("|")[0].strip(); idi = self.cursor.execute("SELECT id_inmueble FROM contratos WHERE id=?", (idc,)).fetchone()[0]
        self.cursor.execute("UPDATE contratos SET activo=0 WHERE id=?", (idc,)); self.cursor.execute("UPDATE inmuebles SET estado='Libre' WHERE id=?", (idi,)); self.conn.commit(); self.act_todo()

    def limpiar_inm(self): self.inm_id_var.set("Nuevo"); [e.delete(0, tk.END) for e in self.inm_ents.values()]
    def limpiar_contrato(self): [e.delete(0, tk.END) for e in self.inq_ents.values()]; self.lbl_v_alq.config(text="$ 0"); self.cb_inm_con.set("")

if __name__ == "__main__":
    root = tk.Tk(); app = SistemaInmobiliaria(root); root.mainloop()
