// Find-and-replace amount_myr_thousands → amount_myr in all measure expressions
var oldRef = "amount_myr_thousands";
var newRef = "amount_myr";

int count = 0;
foreach (var m in Model.AllMeasures)
{
    if (m.Expression.Contains(oldRef))
    {
        m.Expression = m.Expression.Replace(oldRef, newRef);
        count++;
        Output("Updated: " + m.Name);
    }
}

Output("\nTotal measures updated: " + count);