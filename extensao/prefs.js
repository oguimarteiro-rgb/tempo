import Adw from 'gi://Adw';
import Gtk from 'gi://Gtk';
import {ExtensionPreferences} from 'resource:///org/gnome/Shell/Extensions/js/extensions/prefs.js';

export default class TempoPrefs extends ExtensionPreferences {
    fillPreferencesWindow(window) {
        const settings = this.getSettings();
        const page = new Adw.PreferencesPage();
        const group = new Adw.PreferencesGroup({title: 'Atalho'});
        const row = new Adw.EntryRow({
            title: 'Abrir menu (ex.: <Super>t)',
            use_markup: false,
            show_apply_button: true,
            text: settings.get_strv('atalho-menu')[0] ?? '',
        });
        row.connect('apply', () => {
            const texto = row.get_text();
            const [ok, tecla, mods] = Gtk.accelerator_parse(texto);
            if (ok && tecla !== 0 && mods !== 0) {
                row.remove_css_class('error');
                settings.set_strv('atalho-menu', [texto]);
            } else {
                row.add_css_class('error');
            }
        });
        group.add(row);
        page.add(group);
        window.add(page);
    }
}
