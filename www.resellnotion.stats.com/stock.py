@app.route('/statistics')
@login_required
def statistics():
    conn = g.db
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    period = request.args.get('period', 'month')
    start_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    # ÉTAPE 3 : Nouvelles entrées pour la trésorerie réelle
    current_cash = float(request.args.get('current_cash', 0))
    pending_payments = float(request.args.get('pending_payments', 0))

    now_dt = dt.datetime.now()
    today_date = now_dt.date()

    # --- Logique de récupération des ventes et du stock (Inchangée) ---
    # ... (garder tes requêtes SQL habituelles pour 'sales' et 'stock_info') ...

    # 1. Récupération Valeur Stock (Achat)
    cur.execute(
        "SELECT SUM(purchase_price * quantity) as total_value FROM products WHERE user_id = %s AND quantity > 0",
        (current_user.id,))
    stock_res = cur.fetchone()
    valeur_achat_stock = float(stock_res['total_value'] or 0)

    # 2. CALCUL DE LA TRÉSORERIE ENTIÈRE (Base de calcul)
    # Trésorerie de base = Cash + Stock (Achat) + Créances
    total_base_cash = current_cash + valeur_achat_stock + pending_payments

    # 3. CALCUL DES PROJECTIONS SUR LA TRÉSORERIE ENTIÈRE
    # On récupère tes moyennes historiques pour projeter la croissance du capital total
    cur.execute("SELECT MIN(sale_date) as first_sale FROM sales WHERE user_id = %s", (current_user.id,))
    first_res = cur.fetchone()
    first_date = (first_res['first_sale'].date() if isinstance(first_res['first_sale'], dt.datetime) else first_res[
        'first_sale']) if first_res['first_sale'] else today_date
    weeks_active = max(1, (today_date - first_date).days / 7)

    cur.execute("SELECT SUM(sale_price) as total_ca_all FROM sales WHERE user_id = %s", (current_user.id,))
    avg_ca_weekly = float(cur.fetchone()['total_ca_all'] or 0) / weeks_active

    # Flux net hebdo (Profit réinjecté + rotation du capital)
    net_flow_weekly = avg_ca_weekly * 0.25

    proj_1w = total_base_cash + net_flow_weekly
    proj_1m = total_base_cash + (net_flow_weekly * 4.3)
    proj_1y = total_base_cash + (net_flow_weekly * 52)

    return render_template('statistics.html',
                           # ... tes autres variables ...
                           valeur_achat_stock=valeur_achat_stock,
                           current_cash=current_cash,
                           pending_payments=pending_payments,
                           total_base_cash=total_base_cash,
                           proj_1w=proj_1w, proj_1m=proj_1m, proj_1y=proj_1y,
                           avg_ca_weekly=avg_ca_weekly)