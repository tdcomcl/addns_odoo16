odoo.define('l10n_cl_dte_point_of_sale.PartnerDetailsEdit', function (require) {
"use strict";

var PartnerDetailsEdit = require('point_of_sale.PartnerDetailsEdit');
const { _t } = require('web.core');
const Registries = require('point_of_sale.Registries');


const FEPartnerDetailsEdit = (PartnerDetailsEdit) =>
		class extends PartnerDetailsEdit {
			setup() {
				super.setup();
				this.intFields.push('city_id');
				this.intFields.push('activity_description');
				const partner = this.props.partner;
				this.changes.city_id = partner.city_id && partner.city_id[0];
				this.changes.activity_description = partner.activity_description && partner.activity_description[0];
			}
			captureChange(event) {
				super.captureChange(event);
				if ('city_id' === event.target.name && event.target.value && event.target.value !== ''){
					var city = this.env.pos.cities_by_id[event.target.value];
					this.props.partner.city_id = [city.id, city.name]
					this.changes.state_id = city.state_id[0];
					this.props.partner.state_id = city.state_id;
					this.changes.country_id = city.country_id[0];
					this.props.partner.country_id = city.country_id;
					if (!this.props.partner.city || this.props.partner.city === ''){
						this.changes.city = city.name;
						this.props.partner.city = city.name;
					}
					this.render();
				}
				if (['document_number', 'name'].includes(event.target.name)){
					var document_number = event.target.value || '';
					this.changes.vat = document_number;
					this.props.partner.vat = document_number;
					if (this.validar_rut(document_number, event.target.name === 'document_number')){
						document_number = document_number.replace(/[^1234567890Kk]/g, "").toUpperCase();
						this.changes.vat = 'CL' + document_number;
						this.props.partner.vat = 'CL' + document_number;
						document_number = _.str.lpad(document_number, 9, '0');
						document_number = _.str.sprintf('%s.%s.%s-%s',
								document_number.slice(0, 2),
								document_number.slice(2, 5),
								document_number.slice(5, 8),
								document_number.slice(-1)
						)
						this.props.partner.document_number = document_number;
						this.changes.document_number = document_number;
						this.get_remote_data(document_number);
					}
				}
			}

			saveChanges() {
				var self = this;
				let processedChanges = {};
				for (let [key, value] of Object.entries(this.changes)) {
						if (this.intFields.includes(key)) {
								processedChanges[key] = parseInt(value) || false;
						} else {
								processedChanges[key] = value;
						}
				}
				if ((!this.props.partner.name && !processedChanges.name) ||
						processedChanges.name === '' ){
						return this.showPopup('ErrorPopup', {
							title: _('A Customer Name Is Required'),
						});
				}
				processedChanges.id = this.props.partner.id || false;

				if (!this.props.partner.document_number && processedChanges.document_number && !this.props.partner.document_type && !processedChanges.document_type_id) {
					return this.showPopup('ErrorPopup', {
						title: _('Seleccione el tipo de documento')
					});
				}
				if (processedChanges.document_number && processedChanges.document_number !== '' ) {
					processedChanges.document_number = processedChanges.document_number.toUpperCase();
					if (!this.validar_rut(processedChanges.document_number, true)){
						return;
					}
				}
				if (!this.props.partner.country_id && !processedChanges.country_id) {
					return this.showPopup('ErrorPopup', {
						title: _('Seleccione el Pais')}
					);
				}
				if (!this.props.partner.city_id && !processedChanges.city_id) {
					return this.showPopup('ErrorPopup', {
						title: _('Seleccione la comuna')
					});
				}
				if(!this.props.partner.street && !processedChanges.street) {
					return this.showPopup('ErrorPopup', {
						title: _('Ingrese la direccion(calle)')
					});
				}
				if (!this.props.partner.es_mipyme && !processedChanges.es_mipyme && (!this.props.partner.dte_email && !processedChanges.dte_email)) {
					return this.showPopup('ErrorPopup', {
						title: _('Para empresa que no es MiPyme, debe ingrear el correo dte para intercambio')
					});
				}
			this.trigger('save-changes', { processedChanges });
		}

		async get_remote_data(vat){
			const resp = await this.env.services.rpc({
				model: 'res.partner',
				method: 'get_remote_user_data',
				args: [false, vat, false]
			})
			if (resp){
				this.changes.name = resp.razon_social;
				this.props.partner.name = resp.razon_social;
				if (resp.es_mipyme){
					this.changes.es_mipyme = true;
					this.props.partner.es_mipyme = true;
				}else{
					this.changes.es_mipyme = false;
					this.props.partner.es_mipyme = false;
					this.changes.dte_email = resp.dte_email;
					this.props.partner.dte_email = resp.dte_email;
				}
			}
			this.render();
		}

		display_client_details(visibility, partner, clickpos){
				if (visibility === "edit"){
					var state_options = self.$("select[name='state_id']:visible option:not(:first)");
					var comuna_options = self.$("select[name='city_id']:visible option:not(:first)");
					self.$("select[name='country_id']").on('change', function(){
						var select = self.$("select[name='state_id']:visible");
						var selected_state = select.val();
						state_options.detach();
						var displayed_state = state_options.filter("[data-country_id="+(self.$(this).val() || 0)+"]");
						select.val(selected_state);
						displayed_state.appendTo(select).show();
					});
					self.$("select[name='city_id']").on('change', function(){
		        		var city_id = self.$(this).val() || 0;
		        		if (city_id > 0){
		        			var city = self.pos.cities_by_id[city_id];
		        			var select_country = self.$("select[name='country_id']:visible");
		        			select_country.val(city.country_id ? city.country_id[0] : 0);
		        			select_country.change();
		        			var select_state = self.$("select[name='state_id']:visible");
		        			select_state.val(city.state_id ? city.state_id[0] : 0);
		        		}
		        	});
				}
			}

			validar_rut(texto, alert=true){
				var tmpstr = "";
				var i = 0;
				for ( i=0; i < texto.length ; i++ ){
					if ( texto.charAt(i) != ' ' && texto.charAt(i) != '.' && texto.charAt(i) != '-' ){
						tmpstr = tmpstr + texto.charAt(i);
					}
				}
				texto = tmpstr;
				var largo = texto.length;
				if ( largo < 2 ){
	          if (alert){
	          	this.showPopup('ErrorPopup', {
								title: _('Debe ingresar el rut completo')
							});
	          }
					return false;
				}
				for (i=0; i < largo ; i++ ){
					if ( texto.charAt(i) !="0" && texto.charAt(i) != "1" && texto.charAt(i) !="2" && texto.charAt(i) != "3" && texto.charAt(i) != "4" && texto.charAt(i) !="5" && texto.charAt(i) != "6" && texto.charAt(i) != "7" && texto.charAt(i) !="8" && texto.charAt(i) != "9" && texto.charAt(i) !="k" && texto.charAt(i) != "K" ){
					  if (alert){
					    this.showPopup('ErrorPopup', {
								title: _('El valor ingresado no corresponde a un R.U.T valido')
							});
				    }
						return false;
					}
				}
				var j =0;
				var invertido = "";
				for ( i=(largo-1),j=0; i>=0; i--,j++ ){
					invertido = invertido + texto.charAt(i);
				}
				var dtexto = "";
				dtexto = dtexto + invertido.charAt(0);
				dtexto = dtexto + '-';
				var cnt = 0;

				for ( i=1, j=2; i<largo; i++,j++ ){
					// alert("i=[" + i + "] j=[" + j +"]" );
					if ( cnt == 3 ){
						dtexto = dtexto + '.';
						j++;
						dtexto = dtexto + invertido.charAt(i);
						cnt = 1;
					}else{
						dtexto = dtexto + invertido.charAt(i);
						cnt++;
					}
				}

				invertido = "";
				for ( i=(dtexto.length-1),j=0; i>=0; i--,j++ ){
					invertido = invertido + dtexto.charAt(i);
				}
				if ( this.revisarDigito2(texto, alert) ){
					return true;
				}
				return false;
			}

			revisarDigito( dvr, alert){
				var dv = dvr + "";
				if ( dv != '0' && dv != '1' && dv != '2' && dv != '3' && dv != '4' && dv != '5' && dv != '6' && dv != '7' && dv != '8' && dv != '9' && dv != 'k'  && dv != 'K'){
 					if (alert){
						this.showPopup('ErrorPopup', {
							title: _('Debe ingresar un digito verificador valido')
						});
					}
					return false;
				}
				return true;
			}

			revisarDigito2( crut ){
				var largo = crut.length;
				if ( largo < 2 ){
					this.showPopup('ErrorPopup', {
						title: _('Debe ingresar el rut completo')
					});
					return false;
				}
				if ( largo > 2 ){
					var rut = crut.substring(0, largo - 1);
				}else{
					var rut = crut.charAt(0);
				}
				var dv = crut.charAt(largo-1);
				this.revisarDigito( dv );

				if ( rut == null || dv == null ){
					return 0
				}

				var dvr = '0';
				var suma = 0;
				var mul = 2;
				var i = 0;
				for (i= rut.length -1 ; i >= 0; i--){
					suma = suma + rut.charAt(i) * mul;
					if (mul == 7){
						mul = 2;
					}else{
						mul++;
					}
				}
				var res = suma % 11;
				if (res==1){
					dvr = 'k';
				} else if (res==0){
					dvr = '0';
				} else{
					var dvi = 11-res;
					dvr = dvi + "";
				}
				if ( dvr != dv.toLowerCase()){
					this.showPopup('ErrorPopup', {
						title: _('EL rut es incorrecto')
					});
					return false;
				}
				return true;
			}

		}
	Registries.Component.extend(PartnerDetailsEdit, FEPartnerDetailsEdit);

	return FEPartnerDetailsEdit;
});
